import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2.57.4";

const URL=Deno.env.get("SUPABASE_URL")!;
const SERVICE=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const MODEL_NAME="gte-small";
const WORKER_NAME="project_l_semantic_worker";

const db=createClient(URL,SERVICE,{
  auth:{persistSession:false,autoRefreshToken:false}
});
const model=new Supabase.ai.Session(MODEL_NAME);

const json=(body:unknown,status=200)=>new Response(JSON.stringify(body),{
  status,
  headers:{
    "Content-Type":"application/json",
    "Cache-Control":"no-store"
  }
});

const TRANSIENT_CLAIM_CODES=new Set(["57014","PGRST002","PGRST003"]);
const CLAIM_RETRY_DELAY_MS=350;

async function sha256Hex(value:string){
  const bytes=new TextEncoder().encode(value);
  const digest=await crypto.subtle.digest("SHA-256",bytes);
  return Array.from(new Uint8Array(digest))
    .map((b)=>b.toString(16).padStart(2,"0"))
    .join("");
}

async function authorised(req:Request){
  const token=req.headers.get("x-project-l-worker-token")??"";
  if(!token) return {ok:false,tokenPresent:false,tokenLength:0,rpcErrorCode:null,rpcData:null};
  const hash=await sha256Hex(token);
  const {data,error}=await db
    .rpc("project_l_semantic_worker_authorized_v1",{
      p_worker_name:WORKER_NAME,
      p_token_hash:hash
    });
  return {
    ok:!error&&data===true,
    tokenPresent:true,
    tokenLength:token.length,
    rpcErrorCode:error?.code??null,
    rpcData:data===true
  };
}

async function embed(text:string){
  const out=await model.run(text,{
    mean_pool:true,
    normalize:true
  });
  return out as number[];
}

async function claimWithTransientRetry(
  rpcName:string,
  args:Record<string,unknown>,
  stage:string
){
  const first=await db.rpc(rpcName,args);
  if(!first.error){
    return {data:first.data,error:null,deferred:false,code:null};
  }

  const firstCode=String(first.error.code??"");
  if(!TRANSIENT_CLAIM_CODES.has(firstCode)){
    return {data:first.data,error:first.error,deferred:false,code:firstCode||null};
  }

  console.warn(
    "semantic claim transient retry",
    stage,
    firstCode,
    "delayMs="+CLAIM_RETRY_DELAY_MS
  );
  await new Promise((resolve)=>setTimeout(resolve,CLAIM_RETRY_DELAY_MS));

  const second=await db.rpc(rpcName,args);
  if(!second.error){
    return {data:second.data,error:null,deferred:false,code:null};
  }

  const secondCode=String(second.error.code??"");
  if(TRANSIENT_CLAIM_CODES.has(secondCode)){
    console.warn("semantic claim deferred",stage,secondCode);
    return {data:null,error:null,deferred:true,code:secondCode};
  }

  return {data:second.data,error:second.error,deferred:false,code:secondCode||null};
}

Deno.serve(async(req:Request)=>{
  if(req.method!=="POST") return json({error:"METHOD_NOT_ALLOWED"},405);
  const authState=await authorised(req);
  if(!authState.ok) return json({error:"WORKER_AUTH_FAILED"},403);

  const body=await req.json().catch(()=>({})) as Record<string,unknown>;
  const rawEvalLimit=Number(body.evalLimit??8);
  const rawBatchLimit=Number(body.batchLimit??16);
  const evalLimit=Number.isFinite(rawEvalLimit)
    ? Math.min(Math.max(rawEvalLimit,0),16)
    : 8;
  const batchLimit=Number.isFinite(rawBatchLimit)
    ? Math.min(Math.max(rawBatchLimit,0),32)
    : 16;
  const workerId=String(body.workerId??crypto.randomUUID()).slice(0,120);

  let evalClaimed=0;
  let evalCompleted=0;
  let evalFailed=0;
  let unitClaimed=0;
  let unitCompleted=0;
  let unitFailed=0;

  if(evalLimit>0){
    const claimed=await claimWithTransientRetry(
      "project_l_claim_eval_embeddings_v1",
      {
        p_limit:evalLimit,
        p_worker_id:workerId
      },
      "eval"
    );
    if(claimed.deferred){
      return json({
        status:"deferred",
        reason:"transient_database_busy",
        stage:"eval_claim",
        code:claimed.code,
        retryAfterSeconds:1
      },202);
    }
    if(claimed.error){
      console.error("semantic eval claim failed",claimed.code);
      return json({error:"SEMANTIC_EVAL_CLAIM_FAILED"},500);
    }

    const rows=Array.isArray(claimed.data)?claimed.data:[];
    evalClaimed=rows.length;

    for(const row of rows){
      try{
        const vector=await embed(String(row.query_text??""));
        const done=await db.rpc("project_l_complete_eval_embedding_v1",{
          p_id:row.id,
          p_embedding:vector,
          p_model:MODEL_NAME,
          p_worker_id:workerId
        });
        if(done.error||done.data!==true){
          throw new Error(done.error?.code??"eval_complete_rejected");
        }
        evalCompleted++;
      }catch(err){
        evalFailed++;
        const message=err instanceof Error?err.message:String(err);
        await db.rpc("project_l_fail_eval_embedding_v1",{
          p_id:row.id,
          p_error:message,
          p_worker_id:workerId
        });
      }
    }
  }

  if(batchLimit>0){
    const claimed=await claimWithTransientRetry(
      "project_l_claim_semantic_units_v1",
      {
        p_limit:batchLimit,
        p_worker_id:workerId
      },
      "units"
    );
    if(claimed.deferred){
      return json({
        status:"deferred",
        reason:"transient_database_busy",
        stage:"unit_claim",
        code:claimed.code,
        retryAfterSeconds:1,
        eval:{claimed:evalClaimed,completed:evalCompleted,failed:evalFailed}
      },202);
    }
    if(claimed.error){
      console.error("semantic unit claim failed",claimed.code);
      return json({
        error:"SEMANTIC_UNIT_CLAIM_FAILED",
        evalClaimed,evalCompleted,evalFailed
      },500);
    }

    const rows=Array.isArray(claimed.data)?claimed.data:[];
    unitClaimed=rows.length;

    for(const row of rows){
      try{
        const vector=await embed(String(row.input_text??""));
        const done=await db.rpc("project_l_complete_semantic_unit_v1",{
          p_id:row.id,
          p_embedding:vector,
          p_model:MODEL_NAME,
          p_worker_id:workerId
        });
        if(done.error||done.data!==true){
          throw new Error(done.error?.code??"unit_complete_rejected");
        }
        unitCompleted++;
      }catch(err){
        unitFailed++;
        const message=err instanceof Error?err.message:String(err);
        await db.rpc("project_l_fail_semantic_unit_v1",{
          p_id:row.id,
          p_error:message,
          p_worker_id:workerId
        });
      }
    }
  }

  return json({
    status:"ok",
    model:MODEL_NAME,
    eval:{claimed:evalClaimed,completed:evalCompleted,failed:evalFailed},
    units:{claimed:unitClaimed,completed:unitCompleted,failed:unitFailed}
  });
});
