// Repository snapshot derived from deployed Supabase l-companion v27.
// Layer 295 adds runtime lease enforcement; Layer 296 adds served-outcome
// capture; Layer 297 guards renewal timing; Layer 298 requires independent
// privacy-safe query cohorts before evidence can drive a lease transition.
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2.57.4";

const URL=Deno.env.get("SUPABASE_URL")!;
const ANON=Deno.env.get("SUPABASE_ANON_KEY")!;
const SERVICE=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const ID="shine.l";
const DEPLOYMENT_ID=Deno.env.get("DENO_DEPLOYMENT_ID")??"";
const semanticModel=new Supabase.ai.Session("gte-small");
const TABLES=["memory_family","memory_general","memory_health","memory_identity","memory_project_l","memory_recovery","memory_relationships","memory_sport","memory_work"];
const SUPPORTED=["memory_context","context_freshness","memory_ambiguity","identity_transition","correction_review","temporal_fact_discovery","temporal_fact_proposal","temporal_fact_review_packet","temporal_reconciliation_readiness","temporal_reconcile","temporal_transition","temporal_assert_or_observe","temporal_reconfirm","temporal_prompt_control"];

const cors={
  "Access-Control-Allow-Origin":"*",
  "Access-Control-Allow-Headers":"authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods":"POST, OPTIONS"
};
const json=(body:unknown,status=200)=>new Response(JSON.stringify(body),{
  status,headers:{...cors,"Content-Type":"application/json","Cache-Control":"no-store"}
});
const uc=(auth:string)=>createClient(URL,ANON,{
  auth:{persistSession:false,autoRefreshToken:false},
  global:{headers:{Authorization:auth}}
});
const svc=()=>createClient(URL,SERVICE,{auth:{persistSession:false,autoRefreshToken:false}});
const norm=(s:string)=>s.toLowerCase().replace(/[’‘]/g,"'").replace(/[^a-z0-9]+/g," ").replace(/\s+/g," ").trim();
const safe=(v:unknown):Record<string,unknown>=>v&&typeof v==="object"&&!Array.isArray(v)?v as Record<string,unknown>:{};
const str=(...vals:unknown[])=>{for(const v of vals){if(typeof v==="string"&&v.trim())return v.trim();}return "";};
const sha256=async(s:string)=>{
  const bytes=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(s));
  return Array.from(new Uint8Array(bytes)).map(b=>b.toString(16).padStart(2,"0")).join("");
};

function env(operation:string,requestId:string,status:string,capability:string,result:Record<string,unknown>){
  return {
    protocol:"shine-concierge/companion-v1",
    schemaVersion:"1.0.0",
    operation,requestId,status,result,
    provenance:{
      companionId:ID,
      contractVersion:"1.0.0",
      sourceSystem:"Project L",
      capability,
      access:"explicit-purpose-only",
      correctionOwner:capability==="correction_review",
      supersedesInsteadOfOverwrite:true
    }
  };
}

Deno.serve(async(req:Request)=>{
  if(req.method==="OPTIONS") return new Response("ok",{headers:cors});
  if(req.method!=="POST") return json({error:"METHOD_NOT_ALLOWED"},405);

  const auth=req.headers.get("authorization")??"";
  if(!auth.startsWith("Bearer ")) return json({error:"AUTH_REQUIRED"},401);
  const client=uc(auth);
  const {data:u,error:ue}=await client.auth.getUser();
  if(ue||!u.user) return json({error:"AUTH_REQUIRED"},401);

  const body=await req.json().catch(()=>null) as Record<string,unknown>|null;
  if(!body) return json({error:"INVALID_JSON"},400);

  const valid=await client.rpc("concierge_validate_companion_request",{p_envelope:body});
  if(valid.error||valid.data?.valid!==true) return json({error:"INVALID_CONTRACT_ENVELOPE"},400);

  const operation=String(body.operation??"");
  const requestId=String(body.requestId??"");
  const key=String(body.idempotencyKey??"");
  const capability=String(body.capability??"");
  const scope=body.userScope&&typeof body.userScope==="object"?body.userScope as Record<string,unknown>:{};
  if(String(scope.userId??"")!==u.user.id) return json({error:"USER_SCOPE_MISMATCH"},403);
  if(!SUPPORTED.includes(capability)&&operation!=="discover"){
    return json(env(operation,requestId,"rejected",capability,{summary:"Unsupported Project L capability."}));
  }

  const db=svc();
  const cached=key
    ? await db.rpc("project_l_edge_cache_get_v1",{
        p_user:u.user.id,
        p_idempotency_key:key
      })
    : {data:null,error:null};
  if(!cached.error&&cached.data) return json(cached.data);

  const payload=body.payload&&typeof body.payload==="object"?body.payload as Record<string,unknown>:{};
  const input=safe(payload.input);
  const query=str(payload.query,input.query,input.message);
  const reviewId=str(payload.reviewId,input.reviewId);
  const transitionRequestId=str(payload.transitionRequestId,input.transitionRequestId);
  const assertionRequestId=str(payload.assertionRequestId,input.assertionRequestId);
  const reconfirmationRequestId=str(payload.reconfirmationRequestId,input.reconfirmationRequestId);
  const promptControlRequestId=str(payload.promptControlRequestId,input.promptControlRequestId);
  const temporalDiscoveryLimitRaw=Number(payload.limit??input.limit??8);
  const temporalDiscoveryLimit=Number.isInteger(temporalDiscoveryLimitRaw)
    ? Math.min(Math.max(temporalDiscoveryLimitRaw,1),12)
    : 8;
  const temporalReconcilePacketId=str(payload.reviewPacketId,input.reviewPacketId);
  const temporalReconcilePacketUuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(temporalReconcilePacketId)
    ? temporalReconcilePacketId
    : "";
  const temporalReviewCandidateId=str(payload.candidateId,input.candidateId);
  const temporalReviewCandidateUuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(temporalReviewCandidateId)
    ? temporalReviewCandidateId
    : "";
  const temporalProposalSourceTable=str(payload.sourceTable,input.sourceTable);
  const temporalProposalSourceId=str(payload.sourceId,input.sourceId);
  const temporalProposalSubject=str(payload.subject,input.subject);
  const temporalProposalPredicate=str(payload.predicate,input.predicate);
  const temporalProposalClaim=str(payload.claim,input.claim);
  const temporalProposalEffectiveFrom=str(payload.effectiveFrom,input.effectiveFrom);
  const temporalProposalEffectiveTo=str(payload.effectiveTo,input.effectiveTo);
  const temporalProposalMethod=str(payload.method,input.method);
  const temporalProposalEvidenceExcerpt=str(payload.evidenceExcerpt,input.evidenceExcerpt);
  const temporalProposalDateBasis=str(payload.dateBasis,input.dateBasis);
  const temporalProposalConfidenceRaw=payload.confidence??input.confidence;
  const temporalProposalConfidence=Number(temporalProposalConfidenceRaw);
  const temporalProposalMetadata=safe(payload.metadata??input.metadata);
  const temporalDateOk=/^\d{4}-\d{2}-\d{2}$/.test(temporalProposalEffectiveFrom);
  const temporalToOk=!temporalProposalEffectiveTo||/^\d{4}-\d{2}-\d{2}$/.test(temporalProposalEffectiveTo);
  const temporalDateBasisOk=["explicit_source_date","source_observation_date","inferred_relative_date","unknown"].includes(temporalProposalDateBasis);
  const validTemporalProposal=
    Boolean(temporalProposalSourceTable)&&Boolean(temporalProposalSourceId)&&
    Boolean(temporalProposalSubject)&&Boolean(temporalProposalPredicate)&&
    Boolean(temporalProposalClaim)&&Boolean(temporalProposalMethod)&&
    Boolean(temporalProposalEvidenceExcerpt)&&temporalDateOk&&temporalToOk&&
    temporalDateBasisOk&&Number.isFinite(temporalProposalConfidence)&&
    temporalProposalConfidence>=0&&temporalProposalConfidence<=1;
  const ambiguityReason=str(payload.reasonCode,input.reasonCode);
  const ambiguityQueryHash=str(payload.queryHash,input.queryHash);
  const identitySourceReference=Number(payload.sourceReference??input.sourceReference);
  const identityCanonicalKey=str(payload.key,input.key);
  const identityValue=str(payload.value,input.value);
  const identityReason=str(payload.reason,input.reason);
  const identityConfidenceRaw=payload.confidence??input.confidence;
  const identityConfidence=identityConfidenceRaw===undefined||identityConfidenceRaw===null||identityConfidenceRaw===""
    ? 1
    : Number(identityConfidenceRaw);
  const validIdentityTransition=
    Number.isInteger(identitySourceReference)&&identitySourceReference>0&&
    Boolean(identityCanonicalKey)&&Boolean(identityValue)&&Boolean(identityReason)&&
    Number.isFinite(identityConfidence)&&identityConfidence>=0&&identityConfidence<=1;
  const ambiguityRefs=Array.isArray(payload.itemRefs)
    ? payload.itemRefs
    : Array.isArray(input.itemRefs)
      ? input.itemRefs
      : [];
  const suppliedUserRevision=Number(payload.userRevision??input.userRevision);
  const suppliedPolicyRevision=Number(payload.policyRevision??input.policyRevision);
  const hasSuppliedRevision=Number.isInteger(suppliedUserRevision)&&suppliedUserRevision>=1&&Number.isInteger(suppliedPolicyRevision)&&suppliedPolicyRevision>=1;
  const explicit=
    payload.explicitMemoryRequest===true ||
    payload.explicitContextFreshness===true ||
    payload.explicitMemoryAmbiguity===true ||
    payload.explicitIdentityTransition===true ||
    payload.explicitCorrectionReview===true ||
    payload.explicitTemporalFactDiscovery===true ||
    payload.explicitTemporalFactProposal===true ||
    payload.explicitTemporalFactReviewPacket===true ||
    payload.explicitTemporalReconciliationReadiness===true ||
    payload.explicitTemporalReconcile===true ||
    payload.explicitTemporalTransition===true ||
    payload.explicitTemporalAssertion===true ||
    payload.explicitTemporalReconfirmation===true ||
    payload.explicitTemporalPromptControl===true ||
    input.explicitMemoryRequest===true ||
    input.explicitContextFreshness===true ||
    input.explicitMemoryAmbiguity===true ||
    input.explicitIdentityTransition===true ||
    input.explicitCorrectionReview===true ||
    input.explicitTemporalFactDiscovery===true ||
    input.explicitTemporalFactProposal===true ||
    input.explicitTemporalFactReviewPacket===true ||
    input.explicitTemporalReconciliationReadiness===true ||
    input.explicitTemporalReconcile===true ||
    input.explicitTemporalTransition===true ||
    input.explicitTemporalAssertion===true ||
    input.explicitTemporalReconfirmation===true ||
    input.explicitTemporalPromptControl===true;

  let out:Record<string,unknown>;

  if(operation==="discover"){
    out=env(operation,requestId,"ok","memory_context",{
      companionId:ID,
      displayName:"Project L",
      capabilities:[
        {
          id:"memory_context",
          mode:"read",
          sensitive:true,
          requiresExplicitRequest:true,
          requiresConfirmation:false,
          description:"Retrieve owner-bound, permission-scoped memory with evidence provenance, independent corroboration, relevance-guarded diversity, controlled ambiguity, canonical identity, temporal currentness, packet revision fingerprints, and explicit semantic shadow/activation-gate status."
        },
        {
          id:"context_freshness",
          mode:"read",
          sensitive:true,
          requiresExplicitRequest:true,
          requiresConfirmation:false,
          description:"Validate whether a previously issued Project L context packet is still current using its user and policy revision numbers, without re-reading memory."
        },
        {
          id:"memory_ambiguity",
          mode:"action",
          sensitive:true,
          requiresExplicitRequest:true,
          requiresConfirmation:false,
          internalSource:"shine.concierge",
          description:"Open a controlled ambiguity for exact owner-bound memory refs when semantic conflict has genuinely been observed. Project L validates the refs and evidence but never selects truth automatically."
        },
        {
          id:"identity_transition",
          mode:"action",
          sensitive:true,
          requiresExplicitRequest:true,
          requiresConfirmation:false,
          internalSource:"shine.me",
          description:"Create or transition one canonical identity anchor from fidelity-verified direct user evidence. The prior anchor is preserved as SUPERSEDED and the canonical key revision advances."
        },
        {
          id:"correction_review",
          mode:"action",
          sensitive:true,
          requiresExplicitRequest:true,
          requiresConfirmation:false,
          internalSource:"shine.me",
          description:"Review an already user-confirmed Shine Me correction request, preserve the old memory, and apply an approved correction as a canonical overlay."
        },
        {
          id:"temporal_fact_discovery",
          mode:"read",
          sensitive:true,
          requiresExplicitRequest:true,
          requiresConfirmation:false,
          internalSource:"shine.ai",
          description:"Return a bounded queue of owner-bound, direct-user or confirmed-correction memories with strong temporal signals and high extraction suitability. Discovery is read-only and never stages or asserts a fact."
        },
        {
          id:"temporal_fact_proposal",
          mode:"action",
          sensitive:true,
          requiresExplicitRequest:true,
          requiresConfirmation:false,
          internalSource:"shine.ai",
          description:"Validate a structured temporal-fact proposal against one exact direct-user memory. This stages/validates a candidate only; it never asserts a temporal fact, chooses truth, or supersedes history."
        },
        {
          id:"temporal_fact_review_packet",
          mode:"action",
          sensitive:true,
          requiresExplicitRequest:true,
          requiresConfirmation:false,
          internalSource:"shine.ai",
          description:"Prepare an immutable evidence/timeline review packet for one validated temporal-fact candidate and recommend the existing confirmed next workflow. This does not create a Shine Me request or mutate temporal truth."
        },
        {
          id:"temporal_reconciliation_readiness",
          mode:"read",
          sensitive:true,
          requiresExplicitRequest:true,
          requiresConfirmation:false,
          internalSource:"shine.ai",
          description:"Read-only preflight for a consumed temporal review packet. Verifies the external confirmed request and resulting fact/observation without mutating candidate or temporal truth."
        },
        {
          id:"temporal_reconcile",
          mode:"action",
          sensitive:true,
          requiresExplicitRequest:true,
          requiresConfirmation:false,
          internalSource:"shine.ai",
          description:"Close a consumed review packet against an already-completed confirmed Shine Me temporal request. Reconciliation never creates or changes temporal facts; it only verifies lineage and marks the originating candidate asserted when the resulting fact exactly matches."
        },
        {
          id:"temporal_transition",
          mode:"action",
          sensitive:true,
          requiresExplicitRequest:true,
          requiresConfirmation:false,
          internalSource:"shine.me",
          description:"Resolve a confirmed first-person state-change request to one exact current temporal fact and transition it through l_fact_write while preserving history."
        },
        {
          id:"temporal_assert_or_observe",
          mode:"action",
          sensitive:true,
          requiresExplicitRequest:true,
          requiresConfirmation:false,
          internalSource:"shine.me",
          description:"Create a first controlled-template temporal fact, or record a repeated observation when the same current fact is stated again. Different current facts are redirected to the transition path."
        },
        {
          id:"temporal_reconfirm",
          mode:"action",
          sensitive:true,
          requiresExplicitRequest:true,
          requiresConfirmation:false,
          internalSource:"shine.me",
          description:"Reconfirm one exact currently-effective temporal fact as fresh user evidence without changing its effective interval."
        },
        {
          id:"temporal_prompt_control",
          mode:"action",
          sensitive:true,
          requiresExplicitRequest:true,
          requiresConfirmation:false,
          internalSource:"shine.me",
          description:"Apply an exact-fact user preference for optional reconfirmation prompts: snooze, suppress, or resume. Temporal facts and evidence are unchanged."
        }
      ]
    });
  }else if(!explicit){
    out=env(operation,requestId,"rejected",capability,{
      summary:"Project L access requires an explicit memory or correction-review request."
    });
  }else if(operation==="plan"){
    if(capability==="identity_transition"){
      out=env(operation,requestId,validIdentityTransition?"ok":"needs_input",capability,validIdentityTransition?{
        summary:"Project L will verify the cited raw user evidence, then create the canonical identity key or transition its current anchor while preserving history.",
        plan:{
          sourceReference:identitySourceReference,
          canonicalKey:identityCanonicalKey,
          confidence:identityConfidence,
          reason:identityReason,
          fidelityVerifiedDirectUserEvidenceRequired:true,
          oneCurrentAnchorPerCanonicalKey:true,
          historyPreserved:true,
          idempotent:true
        }
      }:{
        summary:"Project L needs a raw source reference, canonical identity key, exact/extracted user value, confidence from 0 to 1, and transition reason.",
        missing:[
          ...(!(Number.isInteger(identitySourceReference)&&identitySourceReference>0)?["payload.sourceReference"]:[]),
          ...(!identityCanonicalKey?["payload.key"]:[]),
          ...(!identityValue?["payload.value"]:[]),
          ...(!identityReason?["payload.reason"]:[]),
          ...(!(Number.isFinite(identityConfidence)&&identityConfidence>=0&&identityConfidence<=1)?["payload.confidence"]:[]
          )
        ]
      });
    }else if(capability==="memory_ambiguity"){
      const validRefs=ambiguityRefs.length>=2&&ambiguityRefs.length<=8;
      const validReason=["explicit_user_conflict","specialist_semantic_conflict","insufficient_disambiguation"].includes(ambiguityReason);
      out=env(operation,requestId,validRefs&&validReason?"ok":"needs_input",capability,validRefs&&validReason?{
        summary:"Project L will validate the exact memory refs, compare their claim hashes and evidence authority, and open an ambiguity only if they are genuinely distinct claims. It will not choose a winner.",
        plan:{
          itemCount:ambiguityRefs.length,
          reasonCode:ambiguityReason,
          automaticTruthSelection:false,
          exactRefsRequired:true,
          duplicateClaimsRejectedAsNotAmbiguous:true,
          correctionCanResolve:true
        }
      }:{
        summary:"Project L needs two to eight exact memory refs and a supported ambiguity reason.",
        missing:[
          ...(validRefs?[]:["payload.itemRefs"]),
          ...(validReason?[]:["payload.reasonCode"])
        ]
      });
    }else if(capability==="context_freshness"){
      out=env(operation,requestId,hasSuppliedRevision?"ok":"needs_input",capability,hasSuppliedRevision?{
        summary:"Project L will compare the supplied context revisions with the current user and policy revisions without re-reading memory.",
        plan:{
          userRevision:suppliedUserRevision,
          policyRevision:suppliedPolicyRevision,
          memoryReadRequired:false,
          returnsChangeSummary:true
        }
      }:{
        summary:"Project L needs both userRevision and policyRevision.",
        missing:["payload.userRevision","payload.policyRevision"]
      });
    }else if(capability==="correction_review"){
      out=env(operation,requestId,reviewId?"ok":"needs_input",capability,reviewId?{
        summary:"Project L will verify the confirmed correction request, bind it to the exact current memory, inspect prior provenance, and either reject/ask for input or supersede it with an auditable correction overlay.",
        plan:{
          reviewId,
          exactBindingRequired:true,
          directUserStatementRequired:true,
          confirmedConciergeTaskRequired:true,
          overwriteLegacyMemory:false,
          appendOnlyAudit:true
        }
      }:{
        summary:"Project L needs a correction review ID.",
        missing:["payload.reviewId"]
      });
    }else if(capability==="temporal_fact_discovery"){
      out=env(operation,requestId,"ok",capability,{
        summary:"Project L will return a bounded, deduplicated queue of high-authority memories with temporal signals, prioritising atomic facts and excluding semantic noise, transport events and interrogative memories.",
        plan:{
          maxCandidates:temporalDiscoveryLimit,
          directUserOrConfirmedCorrectionOnly:true,
          factuallyAssertableOnly:true,
          semanticNoiseExcluded:true,
          exactClaimDeduplication:true,
          atomicMemoriesPreferred:true,
          readOnly:true,
          candidateStaging:false,
          temporalFactMutation:false
        }
      });
    }else if(capability==="temporal_fact_proposal"){
      out=env(operation,requestId,validTemporalProposal&&Boolean(key)?"ok":"needs_input",capability,validTemporalProposal&&Boolean(key)?{
        summary:"Project L will verify the exact memory source, anchor the evidence excerpt, validate the proposed subject/predicate/claim/effective dates, compare it with existing temporal intervals, and stop at a proposal candidate.",
        plan:{
          sourceTable:temporalProposalSourceTable,
          sourceId:temporalProposalSourceId,
          subject:temporalProposalSubject,
          predicate:temporalProposalPredicate,
          effectiveFrom:temporalProposalEffectiveFrom,
          effectiveTo:temporalProposalEffectiveTo||null,
          confidence:temporalProposalConfidence,
          dateBasis:temporalProposalDateBasis,
          directUserEvidenceRequired:true,
          proposalOnly:true,
          assertedFactCreated:false,
          automaticTruthSelection:false,
          temporalAssertionPipelineSeparate:true,
          idempotent:true
        }
      }:{
        summary:"Project L needs an exact memory ref, structured subject/predicate/claim, effective-from date, confidence, evidence excerpt, date basis, extraction method, and idempotency key.",
        missing:[
          ...(!key?["idempotencyKey"]:[]),
          ...(!temporalProposalSourceTable?["payload.sourceTable"]:[]),
          ...(!temporalProposalSourceId?["payload.sourceId"]:[]),
          ...(!temporalProposalSubject?["payload.subject"]:[]),
          ...(!temporalProposalPredicate?["payload.predicate"]:[]),
          ...(!temporalProposalClaim?["payload.claim"]:[]),
          ...(!temporalDateOk?["payload.effectiveFrom"]:[]),
          ...(!temporalToOk?["payload.effectiveTo"]:[]),
          ...(!(Number.isFinite(temporalProposalConfidence)&&temporalProposalConfidence>=0&&temporalProposalConfidence<=1)?["payload.confidence"]:[]),
          ...(!temporalProposalEvidenceExcerpt?["payload.evidenceExcerpt"]:[]),
          ...(!temporalDateBasisOk?["payload.dateBasis"]:[]),
          ...(!temporalProposalMethod?["payload.method"]:[]
          )
        ]
      });
    }else if(capability==="temporal_fact_review_packet"){
      out=env(operation,requestId,Boolean(temporalReviewCandidateUuid)&&Boolean(key)?"ok":"needs_input",capability,Boolean(temporalReviewCandidateUuid)&&Boolean(key)?{
        summary:"Project L will revalidate the candidate against its authoritative source, snapshot the current temporal timeline, and prepare a review packet recommending the existing confirmed workflow. It will not create an assertion/transition request.",
        plan:{
          candidateId:temporalReviewCandidateUuid,
          validatedCandidateRequired:true,
          authoritativeSourceRechecked:true,
          timelineSnapshot:true,
          requestCreated:false,
          confirmationBypassed:false,
          temporalFactMutation:false,
          idempotent:true
        }
      }:{
        summary:"Project L needs a validated temporal candidate UUID and idempotency key.",
        missing:[
          ...(!temporalReviewCandidateUuid?["payload.candidateId"]:[]),
          ...(!key?["idempotencyKey"]:[]
          )
        ]
      });
    }else if(capability==="temporal_reconciliation_readiness"){
      out=env(operation,requestId,temporalReconcilePacketUuid?"ok":"needs_input",capability,temporalReconcilePacketUuid?{
        summary:"Project L will perform a read-only reconciliation preflight against the consumed review packet and its external confirmed request.",
        plan:{
          reviewPacketId:temporalReconcilePacketUuid,
          readOnly:true,
          externalRequestMustExist:true,
          resultingFactMustMatchCandidate:true,
          candidateMutation:false,
          temporalFactMutation:false
        }
      }:{
        summary:"Project L needs the consumed temporal review packet UUID.",
        missing:["payload.reviewPacketId"]
      });
    }else if(capability==="temporal_reconcile"){
      out=env(operation,requestId,temporalReconcilePacketUuid?"ok":"needs_input",capability,temporalReconcilePacketUuid?{
        summary:"Project L will reconcile the originating candidate only against an already-completed confirmed external temporal request. It cannot create or alter the resulting temporal fact.",
        plan:{
          reviewPacketId:temporalReconcilePacketUuid,
          consumedPacketRequired:true,
          confirmedExternalRequestRequired:true,
          exactFactMatchRequired:true,
          createsTemporalFact:false,
          changesTemporalFact:false,
          closesCandidateOnlyAfterVerification:true
        }
      }:{
        summary:"Project L needs the consumed temporal review packet UUID.",
        missing:["payload.reviewPacketId"]
      });
    }else if(capability==="temporal_transition"){
      out=env(operation,requestId,transitionRequestId?"ok":"needs_input",capability,transitionRequestId?{
        summary:"Project L will resolve the request to exactly one temporal fact group and one current fact at the effective date, then apply an explicit transition through l_fact_write.",
        plan:{
          transitionRequestId,
          exactCurrentFactRequired:true,
          confirmedConciergeTaskRequired:true,
          explicitEffectiveDateRequired:true,
          historyPreserved:true,
          writer:"l_fact_write"
        }
      }:{
        summary:"Project L needs a temporal transition request ID.",
        missing:["payload.transitionRequestId"]
      });
    }else if(capability==="temporal_assert_or_observe"){
      out=env(operation,requestId,assertionRequestId?"ok":"needs_input",capability,assertionRequestId?{
        summary:"Project L will validate the controlled preference template, then either create the first temporal fact or record an observation if the same current fact already exists.",
        plan:{
          assertionRequestId,
          duplicateFactsBlocked:true,
          sameCurrentFactBecomesObservation:true,
          differingCurrentFactRequiresTransition:true,
          writer:"l_fact_write",
          observer:"l_fact_observe"
        }
      }:{
        summary:"Project L needs a temporal assertion request ID.",
        missing:["payload.assertionRequestId"]
      });
    }else if(capability==="temporal_reconfirm"){
      out=env(operation,requestId,reconfirmationRequestId?"ok":"needs_input",capability,reconfirmationRequestId?{
        summary:"Project L will verify the exact fact is still current, then record fresh user evidence without changing effective dates or timeline revision.",
        plan:{
          reconfirmationRequestId,
          exactFactBindingRequired:true,
          currentFactRequired:true,
          evidenceOnly:true,
          observer:"l_fact_observe",
          mutatesEffectiveInterval:false
        }
      }:{
        summary:"Project L needs a temporal reconfirmation request ID.",
        missing:["payload.reconfirmationRequestId"]
      });
    }else if(capability==="temporal_prompt_control"){
      out=env(operation,requestId,promptControlRequestId?"ok":"needs_input",capability,promptControlRequestId?{
        summary:"Project L will apply the user's exact-fact reconfirmation prompt preference without changing the fact, evidence, or effective interval.",
        plan:{
          promptControlRequestId,
          controlsPromptingOnly:true,
          temporalFactMutation:false,
          evidenceMutation:false
        }
      }:{
        summary:"Project L needs a temporal prompt-control request ID.",
        missing:["payload.promptControlRequestId"]
      });
    }else{
      out=env(operation,requestId,query?"ok":"needs_input",capability,query?{
        summary:"Project L can search the user's owner-bound, allow-listed promoted memory domains with correction precedence, explicit identity anchors, temporal currentness, and bounded context.",
        plan:{query,maxResults:8,activeOnly:true,bulkExport:false,correctionsPreferred:true}
      }:{
        summary:"Project L needs a memory query.",
        missing:["payload.query"]
      });
    }
  }else if(operation==="result"){
    const prior=await db.rpc("project_l_edge_cache_get_result_v1",{
      p_user:u.user.id,
      p_request_id:requestId
    });
    return json(prior.data??env(operation,requestId,"needs_input",capability,{summary:"No completed Project L result is available yet."}));
  }else if(operation==="execute"&&capability==="identity_transition"){
    if(!validIdentityTransition||!key){
      out=env(operation,requestId,"needs_input",capability,{
        summary:"Project L needs valid identity transition fields and an idempotency key.",
        missing:[
          ...(!key?["idempotencyKey"]:[]),
          ...(!(Number.isInteger(identitySourceReference)&&identitySourceReference>0)?["payload.sourceReference"]:[]),
          ...(!identityCanonicalKey?["payload.key"]:[]),
          ...(!identityValue?["payload.value"]:[]),
          ...(!identityReason?["payload.reason"]:[]),
          ...(!(Number.isFinite(identityConfidence)&&identityConfidence>=0&&identityConfidence<=1)?["payload.confidence"]:[]
          )
        ]
      });
    }else{
      const transitioned=await db.rpc("project_l_edge_transition_identity_v1",{
        p_user:u.user.id,
        p_writer_id:ID,
        p_idempotency_key:key,
        p_source_reference:identitySourceReference,
        p_key:identityCanonicalKey,
        p_value:identityValue,
        p_confidence:identityConfidence,
        p_reason:identityReason,
        p_external_request_id:requestId||null
      });
      if(transitioned.error){
        console.error("Project L identity transition failed",transitioned.error);
        return json({error:"L_IDENTITY_TRANSITION_FAILED"},500);
      }
      const result=safe(transitioned.data);
      const state=String(result.status??"");
      out=env(operation,requestId,"completed",capability,{
        summary:
          state==="transitioned"
            ?"Project L transitioned the canonical identity anchor, preserved the prior anchor as historical, and advanced the key revision."
            : state==="promoted"
              ?"Project L created the first canonical identity anchor for this key."
              : state==="existing"
                ?"Project L found the same canonical identity value already active, so no duplicate anchor was created."
                : state==="review"
                  ?"Project L would not change identity because the direct-user evidence or confidence checks require review."
                  :"Project L could not safely apply the identity transition.",
        ...result,
        memoryOwner:ID,
        historyPreserved:result.historyPreserved===true||state==="existing",
        directOverwritePerformed:false
      });
    }
  }else if(operation==="execute"&&capability==="memory_ambiguity"){
    const validRefs=ambiguityRefs.length>=2&&ambiguityRefs.length<=8;
    const validReason=["explicit_user_conflict","specialist_semantic_conflict","insufficient_disambiguation"].includes(ambiguityReason);
    const requestUuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(requestId)
      ? requestId
      : "";
    if(!validRefs||!validReason||!requestUuid){
      out=env(operation,requestId,"needs_input",capability,{
        summary:"Project L needs a UUID request ID, two to eight exact memory refs, and a supported ambiguity reason.",
        missing:[
          ...(!requestUuid?["requestId"]:[]),
          ...(!validRefs?["payload.itemRefs"]:[]),
          ...(!validReason?["payload.reasonCode"]:[]
          )
        ]
      });
    }else{
      const opened=await db.rpc("project_l_edge_open_ambiguity_v1",{
        p_user:u.user.id,
        p_request_id:requestUuid,
        p_capability:"memory_context",
        p_query_hash:ambiguityQueryHash||null,
        p_reason_code:ambiguityReason,
        p_item_refs:ambiguityRefs
      });
      if(opened.error){
        console.error("Project L ambiguity intake failed",opened.error);
        return json({error:"L_MEMORY_AMBIGUITY_FAILED"},500);
      }
      const result=safe(opened.data);
      const state=String(result.status??"");
      out=env(operation,requestId,"completed",capability,{
        summary:
          state==="open"
            ?"Project L opened a controlled ambiguity. The referenced memories cannot be used as settled factual assertions until clarified or corrected."
            : state==="not_ambiguous"
              ?"Project L found the refs resolve to the same claim, so no ambiguity was opened."
              : state==="resolved"
                ?"Project L found an existing user correction already resolves this conflict."
                :"Project L rejected the ambiguity intake because its exact-ref or evidence checks did not pass.",
        ...result,
        automaticTruthSelection:false
      });
    }
  }else if(operation==="execute"&&capability==="context_freshness"){
    if(!hasSuppliedRevision){
      out=env(operation,requestId,"needs_input",capability,{
        summary:"Project L needs both userRevision and policyRevision.",
        missing:["payload.userRevision","payload.policyRevision"]
      });
    }else{
      const checked=await db.rpc("project_l_edge_context_is_current_v1",{
        p_user:u.user.id,
        p_user_revision:suppliedUserRevision,
        p_policy_revision:suppliedPolicyRevision
      });
      if(checked.error){
        console.error("Project L context freshness check failed",checked.error);
        return json({error:"L_CONTEXT_FRESHNESS_FAILED"},500);
      }
      const result=safe(checked.data);
      const current=result.current===true;
      const currentRevision=safe(result.currentRevision);

      const metric=await db.rpc("project_l_edge_record_freshness_v1",{
        p_payload:{
          user_id:u.user.id,
          request_id:requestId,
          supplied_user_revision:suppliedUserRevision,
          supplied_policy_revision:suppliedPolicyRevision,
          current_user_revision:Number(currentRevision.userRevision??0),
          current_policy_revision:Number(currentRevision.policyRevision??0),
          is_current:current,
          user_revision_current:result.userRevisionCurrent===true,
          policy_revision_current:result.policyRevisionCurrent===true
        }
      });
      if(metric.error||metric.data!==true){
        console.error("Project L context freshness telemetry failed",metric.error?.code??"gateway_rejected");
      }

      out=env(operation,requestId,"completed",capability,{
        summary:current
          ?"The Project L context packet is still current."
          :"The Project L context packet is stale and should be refreshed before reuse.",
        ...result,
        memoryReadPerformed:false
      });
    }
  }else if(operation==="execute"&&capability==="temporal_fact_discovery"){
    const discovered=await db.rpc("project_l_edge_temporal_extraction_discover_v1",{
      p_user:u.user.id,
      p_limit:temporalDiscoveryLimit
    });
    if(discovered.error){
      console.error("Project L temporal fact discovery failed",discovered.error);
      return json({error:"L_TEMPORAL_FACT_DISCOVERY_FAILED"},500);
    }
    const result=safe(discovered.data);
    const candidates=Array.isArray(result.candidates)?result.candidates:[];
    out=env(operation,requestId,"completed",capability,{
      summary:candidates.length>0
        ? `Project L found ${candidates.length} high-signal temporal extraction candidate${candidates.length===1?"":"s"}. No candidate was staged and no temporal fact was created.`
        :"Project L found no unstaged high-signal temporal extraction candidates under the current discovery policy.",
      ...result,
      candidateCount:candidates.length,
      readOnly:true,
      candidateStaging:false,
      assertedFactCreated:false,
      temporalFactMutation:false
    });
  }else if(operation==="execute"&&capability==="temporal_fact_review_packet"){
    if(!temporalReviewCandidateUuid||!key){
      out=env(operation,requestId,"needs_input",capability,{
        summary:"Project L needs a validated temporal candidate UUID and idempotency key.",
        missing:[
          ...(!temporalReviewCandidateUuid?["payload.candidateId"]:[]),
          ...(!key?["idempotencyKey"]:[]
          )
        ],
        requestCreated:false,
        temporalFactChanged:false
      });
    }else{
      const prepared=await db.rpc("project_l_edge_prepare_temporal_review_packet_v1",{
        p_user:u.user.id,
        p_candidate:temporalReviewCandidateUuid,
        p_idempotency_key:key
      });
      if(prepared.error){
        console.error("Project L temporal review packet failed",prepared.error);
        return json({error:"L_TEMPORAL_REVIEW_PACKET_FAILED"},500);
      }
      const result=safe(prepared.data);
      const next=String(result.recommendedNextCapability??"");
      const state=String(result.status??"");
      out=env(operation,requestId,"completed",capability,{
        summary:
          state==="ready"||state==="existing"
            ? next==="temporal_assert_or_observe"
              ?"Project L prepared a review packet for the existing controlled assertion/observation workflow. No request or fact was created."
              : next==="temporal_transition"
                ?"Project L prepared a review packet for the existing confirmed transition workflow. No transition request or fact was created."
                :"Project L prepared the evidence packet, but this predicate has no existing confirmed automatic writer and must remain in structured review."
            :"Project L rejected the review-packet request because the candidate is not currently validated, owned, or source-current.",
        ...result,
        memoryOwner:ID,
        reviewPacketOnly:true,
        requestCreated:false,
        confirmationBypassed:false,
        temporalFactMutation:false
      });
    }
  }else if(operation==="execute"&&capability==="temporal_reconciliation_readiness"){
    if(!temporalReconcilePacketUuid){
      out=env(operation,requestId,"needs_input",capability,{
        summary:"Project L needs the consumed temporal review packet UUID.",
        missing:["payload.reviewPacketId"],
        readOnly:true
      });
    }else{
      const ready=await db.rpc("project_l_edge_temporal_reconciliation_readiness_v1",{
        p_user:u.user.id,
        p_packet:temporalReconcilePacketUuid
      });
      if(ready.error){
        console.error("Project L temporal reconciliation readiness failed",ready.error);
        return json({error:"L_TEMPORAL_RECONCILIATION_READINESS_FAILED"},500);
      }
      out=env(operation,requestId,"completed",capability,{
        summary:String(ready.data?.status??"")==="ready"
          ?"The consumed temporal review packet is ready for deterministic reconciliation."
          :"The temporal review packet is not yet ready for reconciliation.",
        ...safe(ready.data),
        readOnly:true,
        candidateMutation:false,
        temporalFactMutation:false
      });
    }
  }else if(operation==="execute"&&capability==="temporal_reconcile"){
    if(!temporalReconcilePacketUuid){
      out=env(operation,requestId,"needs_input",capability,{
        summary:"Project L needs the consumed temporal review packet UUID.",
        missing:["payload.reviewPacketId"],
        temporalFactMutation:false
      });
    }else{
      const reconciled=await db.rpc("project_l_edge_reconcile_temporal_review_packet_v1",{
        p_user:u.user.id,
        p_packet:temporalReconcilePacketUuid
      });
      if(reconciled.error){
        console.error("Project L temporal reconciliation failed",reconciled.error);
        return json({error:"L_TEMPORAL_RECONCILIATION_FAILED"},500);
      }
      const result=safe(reconciled.data);
      out=env(operation,requestId,"completed",capability,{
        summary:
          result.status==="reconciled"
            ?"Project L verified the confirmed external write and closed the originating candidate against the exact resulting temporal fact."
            : result.status==="observation_only"
              ?"Project L verified the confirmed observation. No new fact was created, so the proposal candidate was not marked asserted."
              :"Project L did not reconcile the candidate because the consumed packet, external request, or resulting fact did not satisfy the lineage checks.",
        ...result,
        reconciliationOnly:true,
        temporalFactCreatedByReconciliation:false,
        temporalFactMutation:false
      });
    }
  }else if(operation==="execute"&&capability==="temporal_fact_proposal"){
    if(!validTemporalProposal||!key){
      out=env(operation,requestId,"needs_input",capability,{
        summary:"Project L needs a complete structured temporal proposal and an idempotency key.",
        missing:[
          ...(!key?["idempotencyKey"]:[]),
          ...(!temporalProposalSourceTable?["payload.sourceTable"]:[]),
          ...(!temporalProposalSourceId?["payload.sourceId"]:[]),
          ...(!temporalProposalSubject?["payload.subject"]:[]),
          ...(!temporalProposalPredicate?["payload.predicate"]:[]),
          ...(!temporalProposalClaim?["payload.claim"]:[]),
          ...(!temporalDateOk?["payload.effectiveFrom"]:[]),
          ...(!temporalToOk?["payload.effectiveTo"]:[]),
          ...(!(Number.isFinite(temporalProposalConfidence)&&temporalProposalConfidence>=0&&temporalProposalConfidence<=1)?["payload.confidence"]:[]),
          ...(!temporalProposalEvidenceExcerpt?["payload.evidenceExcerpt"]:[]),
          ...(!temporalDateBasisOk?["payload.dateBasis"]:[]),
          ...(!temporalProposalMethod?["payload.method"]:[]
          )
        ],
        assertedFactCreated:false
      });
    }else{
      const proposed=await db.rpc("project_l_edge_propose_temporal_fact_v1",{
        p_user:u.user.id,
        p_idempotency_key:key,
        p_source_table:temporalProposalSourceTable,
        p_source_id:temporalProposalSourceId,
        p_subject:temporalProposalSubject,
        p_predicate:temporalProposalPredicate,
        p_claim:temporalProposalClaim,
        p_effective_from:temporalProposalEffectiveFrom,
        p_effective_to:temporalProposalEffectiveTo||null,
        p_confidence:temporalProposalConfidence,
        p_method:temporalProposalMethod,
        p_evidence_excerpt:temporalProposalEvidenceExcerpt,
        p_date_basis:temporalProposalDateBasis,
        p_metadata:{
          ...temporalProposalMetadata,
          requestId,
          proposalOnly:true
        }
      });
      if(proposed.error){
        console.error("Project L temporal fact proposal failed",proposed.error);
        return json({error:"L_TEMPORAL_FACT_PROPOSAL_FAILED"},500);
      }
      const result=safe(proposed.data);
      const state=String(result.status??"");
      out=env(operation,requestId,"completed",capability,{
        summary:
          state==="validated"
            ?"Project L validated the structured temporal proposal. No temporal fact was created; it remains a candidate for the separate assertion/transition pipeline."
            : state==="structured"
              ?"Project L structured the proposal but left it for review because date grounding, confidence, or evidence validation is not strong enough for validated-candidate status."
              : state==="existing"
                ?"Project L found this proposal candidate already staged and returned the existing candidate."
                :"Project L rejected the proposal because its exact-source, evidence, shape, or idempotency checks did not pass.",
        ...result,
        memoryOwner:ID,
        proposalOnly:true,
        assertedFactCreated:false,
        automaticTruthSelection:false,
        temporalFactMutation:false
      });
    }
  }else if(operation==="execute"&&capability==="temporal_prompt_control"){
    if(!promptControlRequestId){
      out=env(operation,requestId,"needs_input",capability,{
        summary:"Project L needs a temporal prompt-control request ID.",
        missing:["payload.promptControlRequestId"],
        promptPreferenceChanged:false,
        temporalFactChanged:false
      });
    }else{
      const controlled=await db.rpc("project_l_apply_temporal_prompt_control",{
        p_prompt_control_request_id:promptControlRequestId,
        p_expected_user_id:u.user.id
      });
      if(controlled.error){
        console.error("Project L temporal prompt control failed",controlled.error);
        return json({error:"L_TEMPORAL_PROMPT_CONTROL_FAILED"},500);
      }
      const result=safe(controlled.data);
      const state=String(result.status??"");
      out=env(operation,requestId,"completed",capability,{
        summary:
          state==="applied"
            ? result.action==="suppress"
              ?"Project L will no longer surface optional reconfirmation prompts for this exact fact unless the user resumes them."
              : result.action==="snooze"
                ?"Project L snoozed optional reconfirmation prompts for this exact fact."
                :"Project L resumed optional reconfirmation prompts for this exact fact."
            : state==="needs_input"
              ?"Project L needs a valid prompt-control duration or action."
              :"Project L rejected the prompt-control request because its binding or confirmation checks did not pass.",
        ...result,
        memoryOwner:ID,
        controlsPromptingOnly:true,
        temporalFactMutation:false,
        evidenceMutation:false
      });
    }
  }else if(operation==="execute"&&capability==="temporal_reconfirm"){
    if(!reconfirmationRequestId){
      out=env(operation,requestId,"needs_input",capability,{
        summary:"Project L needs a temporal reconfirmation request ID.",
        missing:["payload.reconfirmationRequestId"],
        observationRecorded:false,
        temporalFactChanged:false
      });
    }else{
      const reconfirmed=await db.rpc("project_l_apply_temporal_reconfirmation",{
        p_reconfirmation_request_id:reconfirmationRequestId,
        p_expected_user_id:u.user.id
      });
      if(reconfirmed.error){
        console.error("Project L temporal reconfirmation failed",reconfirmed.error);
        return json({error:"L_TEMPORAL_RECONFIRMATION_FAILED"},500);
      }
      const result=safe(reconfirmed.data);
      const state=String(result.status??"");
      out=env(operation,requestId,"completed",capability,{
        summary:
          state==="observed" && result.deduplicated===true
            ?"Project L recognised the reconfirmation, but the fact already had evidence on this Brisbane calendar day so support was not double-counted."
            : state==="observed"
              ?"Project L recorded fresh evidence for the same current temporal fact without changing its effective interval."
              : state==="needs_input"
                ?"Project L could not safely reconfirm the fact because the reply was not a clear positive reaffirmation or the fact is no longer current."
                :"Project L rejected the reconfirmation because its binding or confirmation checks did not pass.",
        ...result,
        memoryOwner:ID,
        temporalObserver:"l_fact_observe",
        evidenceOnly:true,
        effectiveIntervalMutation:false
      });
    }
  }else if(operation==="execute"&&capability==="temporal_assert_or_observe"){
    if(!assertionRequestId){
      out=env(operation,requestId,"needs_input",capability,{
        summary:"Project L needs a temporal assertion request ID.",
        missing:["payload.assertionRequestId"],
        temporalFactChanged:false,
        observationRecorded:false
      });
    }else{
      const applied=await db.rpc("project_l_apply_temporal_assert_or_observe",{
        p_assertion_request_id:assertionRequestId,
        p_expected_user_id:u.user.id
      });
      if(applied.error){
        console.error("Project L temporal assert/observe failed",applied.error);
        return json({error:"L_TEMPORAL_ASSERT_OR_OBSERVE_FAILED"},500);
      }
      const result=safe(applied.data);
      const state=String(result.status??"");
      out=env(operation,requestId,"completed",capability,{
        summary:
          state==="asserted"
            ?"Project L created the first temporal fact for this controlled preference."
            : state==="observed"
              ?"Project L recorded another observation of the same current fact without creating a duplicate or changing its effective dates."
              : state==="needs_input"
                ?"Project L found an existing temporal state that differs or cannot safely be treated as a first assertion."
                :"Project L rejected the assertion because its confirmation, evidence, date, or template checks did not pass.",
        ...result,
        memoryOwner:ID,
        temporalWriter:"l_fact_write",
        temporalObserver:"l_fact_observe",
        duplicateFactsBlocked:true
      });
    }
  }else if(operation==="execute"&&capability==="temporal_transition"){
    if(!transitionRequestId){
      out=env(operation,requestId,"needs_input",capability,{
        summary:"Project L needs a temporal transition request ID.",
        missing:["payload.transitionRequestId"],
        temporalFactChanged:false
      });
    }else{
      const transitioned=await db.rpc("project_l_apply_temporal_transition",{
        p_transition_request_id:transitionRequestId,
        p_expected_user_id:u.user.id
      });
      if(transitioned.error){
        console.error("Project L temporal transition failed",transitioned.error);
        return json({error:"L_TEMPORAL_TRANSITION_FAILED"},500);
      }
      const result=safe(transitioned.data);
      const state=String(result.status??"");
      out=env(operation,requestId,"completed",capability,{
        summary:
          state==="applied"
            ?"Project L applied the state change as a temporal transition. The prior fact remains historical and the new fact is current from its effective date."
            : state==="needs_input"
              ?"Project L could not safely bind the change to one exact current temporal fact."
              :"Project L rejected the temporal transition because its confirmation or evidence checks did not pass.",
        ...result,
        memoryOwner:ID,
        temporalWriter:"l_fact_write",
        historyPreserved:result.historyPreserved===true
      });
    }
  }else if(operation==="execute"&&capability==="correction_review"){
    if(!reviewId){
      out=env(operation,requestId,"needs_input",capability,{
        summary:"Project L needs a correction review ID.",
        missing:["payload.reviewId"],
        memoryChanged:false
      });
    }else{
      const reviewed=await db.rpc("project_l_edge_review_correction_v1",{
        p_review_id:reviewId,
        p_expected_user_id:u.user.id
      });
      if(reviewed.error){
        console.error("Project L correction review failed",reviewed.error);
        return json({error:"L_CORRECTION_REVIEW_FAILED"},500);
      }
      const result=safe(reviewed.data);
      const state=String(result.status??"");
      out=env(operation,requestId,"completed",capability,{
        summary:
          state==="applied"
            ?"Project L approved the correction, preserved the previous memory as SUPERSEDED, and activated the corrected memory overlay."
            : state==="needs_input"
              ?"Project L could not safely apply the correction without more exact user evidence."
              :"Project L rejected the correction because its safety or evidence checks did not pass.",
        ...result,
        memoryOwner:ID,
        legacyOverwritePerformed:false,
        auditTrail:"project_l_memory_correction_audit"
      });
    }
  }else if(operation==="execute"){
    if(!query){
      out=env(operation,requestId,"needs_input",capability,{
        summary:"Project L needs a memory query.",
        missing:["payload.query"]
      });
    }else{
      const stop=new Set(["what","when","where","about","tell","show","from","with","the","memory","please","could","would"]);
      const baseTokens=norm(query).split(" ").filter(x=>x.length>=2);
      const filtered=baseTokens.filter(x=>x.length>2&&!stop.has(x));
      const tokens=(filtered.length?filtered:baseTokens).slice(0,32);

      let semanticGate:Record<string,unknown>={
        available:false,
        servingMode:"shadow_only",
        productionSemanticEnabled:false,
        reason:"semantic_gate_unavailable"
      };
      const semanticGateResult=await db.rpc("project_l_edge_semantic_gate_status_v2",{
        p_deployment_id:DEPLOYMENT_ID
      });
      if(!semanticGateResult.error&&semanticGateResult.data&&typeof semanticGateResult.data==="object"){
        semanticGate={
          available:true,
          ...(semanticGateResult.data as Record<string,unknown>)
        };
      }else if(semanticGateResult.error){
        console.error("Project L semantic gate lookup failed",semanticGateResult.error.code);
      }
      const semanticCoverage=safe(semanticGate.coverage);

      // Layer 295 — runtime lease enforcement.
      // This is deliberately read-only: learning/renewal remain in Layers 293/294.
      const explicitRetrievalModeRaw=String(
        payload.retrievalMode??payload.retrieval_mode??""
      ).trim().toLowerCase();
      const retrievalIntentRaw=String(
        payload.retrievalIntent??payload.retrieval_intent??"general_recall"
      );
      const retrievalIntent=
        norm(retrievalIntentRaw).replaceAll(" ","_").slice(0,80)||
        "general_recall";
      const runtimeDefaultMode=
        semanticGate.productionSemanticEnabled===true?"semantic":"lexical";

      let runtimeRetrievalDecision:Record<string,unknown>={
        available:false,
        status:"default",
        effectiveMode:runtimeDefaultMode,
        source:"runtime_default",
        reason:"runtime_retrieval_decision_unavailable",
        leaseApplied:false
      };

      const runtimeDecisionResult=await db.rpc(
        "project_l_runtime_retrieval_decision_v1",
        {
          p_user:u.user.id,
          p_intent:retrievalIntent,
          p_explicit_mode:explicitRetrievalModeRaw||null,
          p_default_mode:runtimeDefaultMode,
          p_semantic_ready:semanticGate.productionSemanticEnabled===true,
          p_hybrid_ready:false,
          p_now:new Date().toISOString()
        }
      );

      if(
        !runtimeDecisionResult.error &&
        runtimeDecisionResult.data &&
        typeof runtimeDecisionResult.data==="object"
      ){
        runtimeRetrievalDecision={
          available:true,
          ...(runtimeDecisionResult.data as Record<string,unknown>)
        };
      }else if(runtimeDecisionResult.error){
        console.error(
          "Project L runtime retrieval decision unavailable",
          runtimeDecisionResult.error.code
        );
      }

      const selectedRetrievalMode=
        runtimeRetrievalDecision.effectiveMode==="semantic" &&
        semanticGate.productionSemanticEnabled===true
          ?"semantic"
          :"lexical";

      let liveRetrievalMethod="lexical_context_v7";
      let semanticResultsInfluencedThisResponse=false;
      let semanticFallbackReason="";
      let semanticEmbeddingMs:number|null=null;
      let semanticContextMs:number|null=null;
      let semanticQueryCacheHit:boolean|null=null;
      let memory:any=null;

      const lexicalMemory=async()=>await db.rpc("project_l_edge_memory_context_v1",{
        p_user:u.user.id,
        p_terms:tokens,
        p_limit:8,
        p_identity_limit:4,
        p_char_budget:10000
      });

      if(
        selectedRetrievalMode==="semantic" &&
        semanticGate.productionSemanticEnabled===true
      ){
        try{
          const semanticGeneration=String(semanticGate.embeddingGeneration??"gte-small-384-v1");
          const queryHash=await sha256(semanticGeneration+"|"+norm(query));
          const cacheStart=performance.now();
          const cachedMemory=await db.rpc("project_l_edge_memory_context_semantic_cached_v1",{
            p_user:u.user.id,
            p_query_hash:queryHash,
            p_terms:tokens,
            p_limit:8,
            p_identity_limit:4,
            p_char_budget:10000
          });
          const cachedData=safe(cachedMemory.data);
          const cachedMatches=Array.isArray(cachedData.matches)
            ? cachedData.matches
            : [];

          if(
            !cachedMemory.error &&
            cachedData.status==="ok" &&
            cachedMatches.length>0
          ){
            memory=cachedMemory;
            semanticQueryCacheHit=true;
            semanticEmbeddingMs=0;
            semanticContextMs=Math.round((performance.now()-cacheStart)*100)/100;
            liveRetrievalMethod="semantic_gte_small_cached";
            semanticResultsInfluencedThisResponse=true;
          }else{
            semanticQueryCacheHit=false;
            const embedStart=performance.now();
            const embedding=await semanticModel.run(query,{
              mean_pool:true,
              normalize:true
            });
            semanticEmbeddingMs=Math.round((performance.now()-embedStart)*100)/100;

            const cacheWrite=await db.rpc("project_l_edge_semantic_query_cache_put_v1",{
              p_user:u.user.id,
              p_query_hash:queryHash,
              p_embedding:embedding
            });
            if(cacheWrite.error||cacheWrite.data!==true){
              console.error(
                "Project L semantic query cache write failed",
                cacheWrite.error?.code??"cache_write_rejected"
              );
            }

            const semanticStart=performance.now();
            const semanticMemory=await db.rpc("project_l_edge_memory_context_semantic_v1",{
              p_user:u.user.id,
              p_embedding:embedding,
              p_terms:tokens,
              p_limit:8,
              p_identity_limit:4,
              p_char_budget:10000
            });
            semanticContextMs=Math.round((performance.now()-semanticStart)*100)/100;

            const semanticData=safe(semanticMemory.data);
            const semanticMatches=Array.isArray(semanticData.matches)
              ? semanticData.matches
              : [];

            if(
              semanticMemory.error ||
              semanticData.status!=="ok" ||
              semanticMatches.length===0
            ){
              semanticFallbackReason=semanticMemory.error
                ? "semantic_context_error"
                : semanticData.status!=="ok"
                  ? "semantic_context_not_ok"
                  : "semantic_context_empty";
              console.error(
                "Project L semantic context fallback",
                semanticMemory.error?.code??semanticFallbackReason
              );
              memory=await lexicalMemory();
              liveRetrievalMethod="lexical_context_v7_fallback";
            }else{
              memory=semanticMemory;
              liveRetrievalMethod="semantic_gte_small";
              semanticResultsInfluencedThisResponse=true;
            }
          }
        }catch(err){
          semanticFallbackReason="semantic_embedding_or_runtime_error";
          console.error(
            "Project L semantic retrieval fallback",
            err instanceof Error ? err.message : String(err)
          );
          memory=await lexicalMemory();
          liveRetrievalMethod="lexical_context_v7_fallback";
        }
      }else{
        memory=await lexicalMemory();
      }

      if(memory?.error){
        console.error("Project L memory context failed",memory.error);
        return json({error:"L_MEMORY_CONTEXT_FAILED"},500);
      }

      const memoryData=safe(memory?.data);
      const matches=Array.isArray(memoryData.matches)
        ? memoryData.matches as Record<string,unknown>[]
        : [];
      const identityAnchors=Array.isArray(memoryData.identityAnchors)
        ? memoryData.identityAnchors as Record<string,unknown>[]
        : [];
      const memoryScope=safe(memoryData.scope);
      const compression=safe(memoryData.compression);
      const contextRevision=safe(memoryData.contextRevision);
      const identityInjection=safe(memoryData.identityInjection);
      const retrievalDiversity=safe(memoryData.retrievalDiversity);

      const reconciliationSummary=matches.reduce((acc:any,item:any)=>{
        const r=safe(item.reconciliation);
        if(r.safeForFactualAssertion===true) acc.safeForFactualAssertion+=1;
        if(r.claimHasIndependentCorroboration===true) acc.independentlyCorroborated+=1;
        if(r.requiresCorroborationBeforeAssertion===true) acc.needsCorroboration+=1;
        return acc;
      },{safeForFactualAssertion:0,independentlyCorroborated:0,needsCorroboration:0});

      // Layer 296 — capture content-free served retrieval outcomes and feed
      // only genuine active-lease service into Layer 294 renewal evaluation.
      let servedOutcome:Record<string,unknown>={
        available:false,
        reason:"served_outcome_capture_unavailable"
      };
      let strategyLeaseEvaluation:Record<string,unknown>={
        available:false,
        reason:"renewal_feed_unavailable"
      };
      const servedAt=new Date().toISOString();

      const servedQueryFingerprint=await sha256(
        "layer298-query-v1|"+norm(query)
      );

      const outcomeRecord=await db.rpc(
        "project_l_record_served_outcome_bound_v1",
        {
          p_user:u.user.id,
          p_request_id:requestId,
          p_intent:retrievalIntent,
          p_mode:selectedRetrievalMode,
          p_query_fingerprint:servedQueryFingerprint,
          p_payload:{
            returned_count:matches.length,
            safe_assertion_count:reconciliationSummary.safeForFactualAssertion,
            corroborated_count:reconciliationSummary.independentlyCorroborated,
            needs_corroboration_count:reconciliationSummary.needsCorroboration,
            unique_domain_count:Number(retrievalDiversity.uniqueDomains??0),
            unique_subject_count:Number(retrievalDiversity.uniqueSubjects??0),
            diversity_fallback_used:retrievalDiversity.fallbackUsed===true,
            retrieval_fallback_used:liveRetrievalMethod.includes("fallback"),
            cache_hit:semanticQueryCacheHit,
            runtime_strategy_source:String(
              runtimeRetrievalDecision.source??"runtime_default"
            ),
            runtime_strategy_reason:String(
              runtimeRetrievalDecision.reason??"runtime_retrieval_decision_unavailable"
            ),
            lease_applied:runtimeRetrievalDecision.leaseApplied===true,
            explicit_mode_used:explicitRetrievalModeRaw.length>0
          },
          p_served_at:servedAt
        }
      );

      if(
        !outcomeRecord.error &&
        outcomeRecord.data &&
        typeof outcomeRecord.data==="object"
      ){
        servedOutcome={
          available:true,
          ...(outcomeRecord.data as Record<string,unknown>)
        };

        const renewalFeed=await db.rpc(
          "project_l_governed_lease_evaluation_v1",
          {
            p_user:u.user.id,
            p_intent:retrievalIntent,
            p_request_id:requestId,
            p_now:servedAt
          }
        );

        if(
          !renewalFeed.error &&
          renewalFeed.data &&
          typeof renewalFeed.data==="object"
        ){
          strategyLeaseEvaluation={
            available:true,
            ...(renewalFeed.data as Record<string,unknown>)
          };
        }else if(renewalFeed.error){
          console.error(
            "Project L governed lease evaluation unavailable",
            renewalFeed.error.code
          );
        }
      }else if(outcomeRecord.error){
        console.error(
          "Project L served outcome capture unavailable",
          outcomeRecord.error.code
        );
      }

      let temporalContext:Record<string,unknown>={
        available:false,
        reason:"no_specific_temporal_terms"
      };
      if(tokens.length>0){
        const temporal=await db.rpc("l_temporal_context",{
          p_user:u.user.id,
          p_terms:tokens.slice(0,24),
          p_as_of:null,
          p_limit:8
        });
        if(!temporal.error && temporal.data && typeof temporal.data==="object"){
          const temporalData=temporal.data as Record<string,unknown>;
          const temporalGroups=Array.isArray(temporalData.groups)
            ? temporalData.groups as Record<string,unknown>[]
            : [];
          const factIds=[...new Set(
            temporalGroups.flatMap((group)=>{
              const buckets=["current","historical","later","correctedHistory"];
              return buckets.flatMap((bucket)=>{
                const rows=Array.isArray(group[bucket])
                  ? group[bucket] as Record<string,unknown>[]
                  : [];
                return rows
                  .map((row)=>String(row.id??""))
                  .filter((id)=>/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(id));
              });
            })
          )].slice(0,64);

          let support:Record<string,unknown>={
            available:false,
            reason:"no_temporal_fact_ids"
          };
          if(factIds.length>0){
            const supportResult=await db.rpc("l_temporal_fact_support",{
              p_user:u.user.id,
              p_fact_ids:factIds,
              p_as_of:typeof temporalData.asOf==="string" ? temporalData.asOf : null
            });
            if(!supportResult.error && supportResult.data && typeof supportResult.data==="object"){
              support={
                available:true,
                ...(supportResult.data as Record<string,unknown>)
              };
            }else if(supportResult.error){
              console.error("Project L temporal support lookup failed",supportResult.error);
              support={
                available:false,
                reason:"temporal_support_unavailable"
              };
            }
          }

          temporalContext={
            available:true,
            ...temporalData,
            support
          };
        }else if(temporal.error){
          console.error("Project L temporal context lookup failed",temporal.error);
          temporalContext={
            available:false,
            reason:"temporal_context_unavailable"
          };
        }
      }

      const metric=await db.rpc("project_l_edge_record_context_run_v1",{
        p_payload:{
          user_id:u.user.id,
          request_id:requestId,
          term_count:tokens.length,
          allowed_domain_count:Number(memoryScope.allowedDomainCount??0),
          candidate_count:Number(memoryData.returnedCount??matches.length),
          returned_count:matches.length,
          identity_anchor_count:identityAnchors.length,
          source_chars:Number(compression.sourceChars??0),
          returned_chars:Number(compression.returnedChars??0),
          compression_ratio:typeof compression.ratio==="number"?compression.ratio:null,
          temporal_context_available:temporalContext.available===true,
          status:String(memoryData.status??"completed"),
          user_revision:Number(contextRevision.userRevision??0)||null,
          policy_revision:Number(contextRevision.policyRevision??0)||null,
          context_fingerprint:typeof contextRevision.fingerprint==="string"?contextRevision.fingerprint:null,
          safe_assertion_count:reconciliationSummary.safeForFactualAssertion,
          corroborated_count:reconciliationSummary.independentlyCorroborated,
          needs_corroboration_count:reconciliationSummary.needsCorroboration,
          identity_query_relevant_count:Number(identityInjection.queryRelevantCount??0),
          identity_baseline_count:Number(identityInjection.baselineCount??0),
          unique_domain_count:Number(retrievalDiversity.uniqueDomains??0)||null,
          unique_subject_count:Number(retrievalDiversity.uniqueSubjects??0)||null,
          max_domain_count:Number(retrievalDiversity.maxItemsFromOneDomain??0)||null,
          max_subject_count:Number(retrievalDiversity.maxItemsFromOneSubject??0)||null,
          diversity_promoted_count:Number(retrievalDiversity.diversityPromotedItems??0),
          diversity_fallback_used:retrievalDiversity.fallbackUsed===true,
          semantic_gate_eligible:semanticGate.eligible===true,
          semantic_serving_mode:String(semanticGate.servingMode??"shadow_only"),
          semantic_production_enabled:semanticGate.productionSemanticEnabled===true,
          semantic_unique_input_coverage:
            typeof semanticCoverage.uniqueInputCoverage==="number"
              ? semanticCoverage.uniqueInputCoverage
              : null,
          semantic_unit_coverage:
            typeof semanticCoverage.unitCoverage==="number"
              ? semanticCoverage.unitCoverage
              : null,
          semantic_runtime_path_ready:semanticGate.runtimePathReady===true,
          runtime_strategy_available:runtimeRetrievalDecision.available===true,
          runtime_strategy_source:String(runtimeRetrievalDecision.source??"runtime_default"),
          runtime_strategy_effective_mode:selectedRetrievalMode,
          runtime_strategy_reason:String(
            runtimeRetrievalDecision.reason??"runtime_retrieval_decision_unavailable"
          ),
          runtime_strategy_lease_applied:runtimeRetrievalDecision.leaseApplied===true,
          served_outcome_captured:servedOutcome.available===true,
          served_outcome_quality_score:
            typeof servedOutcome.qualityScore==="number"
              ? servedOutcome.qualityScore
              : null,
          served_outcome_renewal_eligible:servedOutcome.renewalEligible===true,
          lease_feed_available:strategyLeaseEvaluation.available===true,
          lease_feed_status:String(strategyLeaseEvaluation.status??"unavailable"),
          semantic_query_cache_hit:semanticQueryCacheHit,
          semantic_embedding_ms:semanticEmbeddingMs,
          semantic_context_ms:semanticContextMs
        }
      });
      if(metric.error||metric.data!==true){
        console.error("Project L memory context telemetry failed",metric.error?.code??"gateway_rejected");
      }

      out=env(operation,requestId,"completed",capability,{
        summary:matches.length
          ?"Project L found "+matches.length+" owner-bound, permission-scoped memory items."
          :"Project L found no matching promoted memory in the allowed scope.",
        query,
        identityAnchors,
        temporalContext,
        matches,
        authorityPolicy:memoryData.authorityPolicy??{},
        freshnessPolicy:memoryData.freshnessPolicy??{},
        compression,
        contextRevision,
        reconciliationSummary,
        reconciliationPolicy:memoryData.reconciliationPolicy??{},
        identityInjection,
        retrievalDiversity,
        retrievalLearning:{
          servedOutcome,
          strategyLeaseEvaluation
        },
        semanticRetrieval:{
          ...semanticGate,
          runtimeRetrievalDecision,
          selectedRetrievalMode,
          liveRetrievalMethod,
          semanticResultsInfluencedThisResponse,
          semanticFallbackReason:semanticFallbackReason||null,
          semanticQueryCacheHit,
          semanticEmbeddingMs,
          semanticContextMs
        },
        scope:{
          ...memoryScope,
          shortTermIncluded:false,
          quarantineIncluded:false,
          supersededIncluded:false,
          identityAnchorsIncluded:identityAnchors.length>0,
          temporalFactsIncluded:temporalContext.available===true,
          semanticShadowStatusIncluded:semanticGate.available===true,
          temporalEvidenceSupportIncluded:
            temporalContext.available===true &&
            typeof temporalContext.support==="object"
        }
      });
    }
  }else{
    return json({error:"UNSUPPORTED_OPERATION"},400);
  }

  if(key){
    const cachedWrite=await db.rpc("project_l_edge_cache_upsert_v1",{
      p_user:u.user.id,
      p_idempotency_key:key,
      p_request_id:requestId,
      p_operation:operation,
      p_response_envelope:out
    });
    if(cachedWrite.error||cachedWrite.data!==true){
      console.error("Project L response cache write failed",cachedWrite.error?.code??"gateway_rejected");
    }
  }
  return json(out);
});