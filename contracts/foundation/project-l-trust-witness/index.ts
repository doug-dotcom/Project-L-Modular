import postgres from 'npm:postgres@3.4.9';

const MAX_BODY_BYTES = 16 * 1024;
const WITNESS_ID = 'foundation-project-l';

const dbUrl = Deno.env.get('SUPABASE_DB_URL');
if (!dbUrl) throw new Error('Missing SUPABASE_DB_URL');

const rawSql = postgres(dbUrl, {
  max: 1,
  prepare: false,
  idle_timeout: 20,
  connect_timeout: 10,
});

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'cache-control': 'no-store',
      'x-content-type-options': 'nosniff',
    },
  });

const runAsGateway = async <T>(
  fn: (tx: any) => Promise<T>,
): Promise<T> =>
  rawSql.begin(async (tx: any) => {
    await tx.unsafe('set local role foundation_gateway');
    return fn(tx);
  });

const clientToken = (request: Request): string =>
  (request.headers.get('x-shine-client-token') ?? '').trim();

const readJson = async (request: Request): Promise<Record<string, unknown>> => {
  const declared = request.headers.get('content-length');
  if (declared !== null && Number(declared) > MAX_BODY_BYTES) {
    throw new Error('body-too-large');
  }
  const text = await request.text();
  if (new TextEncoder().encode(text).byteLength > MAX_BODY_BYTES) {
    throw new Error('body-too-large');
  }
  const value = text ? JSON.parse(text) : {};
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('invalid-json');
  }
  return value as Record<string, unknown>;
};

Deno.serve(async (request: Request) => {
  const token = clientToken(request);
  if (token.length < 32) {
    return json({ status: 'denied', reasonCode: 'witness-client-unverified' }, 401);
  }

  const url = new URL(request.url);

  try {
    if (request.method === 'GET') {
      const witnessId = (url.searchParams.get('witnessId') || WITNESS_ID).trim();
      const rows = await runAsGateway((tx) =>
        tx`select foundation.project_l_trace_witness_current_v1(
          ${token},
          ${witnessId}
        ) as result`
      );
      const result = rows?.[0]?.result;
      if (!result || typeof result !== 'object') {
        return json({ status: 'unavailable', reasonCode: 'witness-result-invalid' }, 503);
      }
      const status = result.status === 'denied' ? 401 : 200;
      return json(result, status);
    }

    if (request.method === 'POST') {
      const body = await readJson(request);
      const operation = String(body.operation || '').trim();

      if (operation === 'external-roster-head-current') {
        const witnessId = String(
          body.witnessId || 'foundation-project-l-roster-head'
        ).trim();
        const rows = await runAsGateway((tx) =>
          tx`select foundation.project_l_roster_head_witness_current_v1(
            ${token},
            ${witnessId}
          ) as result`
        );
        const result = rows?.[0]?.result;
        if (!result || typeof result !== 'object') {
          return json(
            { status: 'unavailable', reasonCode: 'witness-result-invalid' },
            503,
          );
        }
        const status =
          result.status === 'denied' ? 401 :
          result.status === 'invalid' ? 400 :
          result.status === 'unavailable' ? 503 :
          200;
        return json(result, status);
      }

      if (operation === 'external-roster-head-record') {
        const witnessId = String(
          body.witnessId || 'foundation-project-l-roster-head'
        ).trim();
        const sequence = Number(body.sequence);
        const headSha256 = String(body.headSha256 || '');
        const generation = Number(body.generation);
        const policySha256 = String(body.policySha256 || '');
        const stateSha256 = String(body.stateSha256 || '');
        if (
          !Number.isInteger(sequence) ||
          !Number.isInteger(generation) ||
          sequence < 1 ||
          generation < 1
        ) {
          return json(
            { status: 'invalid', reasonCode: 'roster-head-witness-request-invalid' },
            400,
          );
        }
        const rows = await runAsGateway((tx) =>
          tx`select foundation.project_l_roster_head_witness_record_v1(
            ${token},
            ${witnessId},
            ${sequence},
            ${headSha256},
            ${generation},
            ${policySha256},
            ${stateSha256}
          ) as result`
        );
        const result = rows?.[0]?.result;
        if (!result || typeof result !== 'object') {
          return json(
            { status: 'unavailable', reasonCode: 'witness-result-invalid' },
            503,
          );
        }
        const status =
          result.status === 'denied' ? 401 :
          result.status === 'invalid' ? 400 :
          result.status === 'rejected' ? 409 :
          result.status === 'unavailable' ? 503 :
          200;
        return json(result, status);
      }

      if (operation === 'external-roster-transition-authorize') {
        const previousPolicy = body.previousPolicy;
        const nextPolicy = body.nextPolicy;
        const rows = await runAsGateway((tx) =>
          tx`select foundation.project_l_external_roster_transition_authorize_v1(
            ${token},
            ${JSON.stringify(previousPolicy)}::jsonb,
            ${JSON.stringify(nextPolicy)}::jsonb
          ) as result`
        );
        const result = rows?.[0]?.result;
        if (!result || typeof result !== 'object') {
          return json(
            { status: 'unavailable', reasonCode: 'witness-result-invalid' },
            503,
          );
        }
        const status =
          result.status === 'denied' ? 401 :
          result.status === 'invalid' ? 400 :
          result.status === 'unavailable' ? 503 :
          200;
        return json(result, status);
      }

      if (operation === 'policy-transition-authorize') {
        const previousPolicy = body.previousPolicy;
        const nextPolicy = body.nextPolicy;
        const rows = await runAsGateway((tx) =>
          tx`select foundation.project_l_policy_transition_authorize_v1(
            ${token},
            ${JSON.stringify(previousPolicy)}::jsonb,
            ${JSON.stringify(nextPolicy)}::jsonb
          ) as result`
        );
        const result = rows?.[0]?.result;
        if (!result || typeof result !== 'object') {
          return json(
            { status: 'unavailable', reasonCode: 'witness-result-invalid' },
            503,
          );
        }
        const status =
          result.status === 'denied' ? 401 :
          result.status === 'invalid' ? 400 :
          result.status === 'unavailable' ? 503 :
          200;
        return json(result, status);
      }

      if (operation === 'policy-transition-verify') {
        const previousPolicy = body.previousPolicy;
        const nextPolicy = body.nextPolicy;
        const authorization = body.authorization;
        const rows = await runAsGateway((tx) =>
          tx`select foundation.project_l_policy_transition_verify_v1(
            ${token},
            ${JSON.stringify(previousPolicy)}::jsonb,
            ${JSON.stringify(nextPolicy)}::jsonb,
            ${JSON.stringify(authorization)}::jsonb
          ) as result`
        );
        const result = rows?.[0]?.result;
        if (!result || typeof result !== 'object') {
          return json(
            { status: 'unavailable', reasonCode: 'witness-result-invalid' },
            503,
          );
        }
        const status =
          result.status === 'denied' ? 401 :
          result.status === 'invalid' ? 400 :
          result.status === 'unavailable' ? 503 :
          200;
        return json(result, status);
      }

      const witnessId = String(body.witnessId || WITNESS_ID);
      const sequence = Number(body.sequence);
      const headSha256 = String(body.headSha256 || '');
      const generation = Number(body.generation);
      const keysetSha256 = String(body.keyset_sha256 || '');
      const stateSha256 = String(body.stateSha256 || '');

      if (
        !Number.isInteger(sequence) ||
        !Number.isInteger(generation) ||
        sequence < 1 ||
        generation < 1
      ) {
        return json({ status: 'invalid', reasonCode: 'witness-request-invalid' }, 400);
      }

      const rows = await runAsGateway((tx) =>
        tx`select foundation.project_l_trace_witness_record_v1(
          ${token},
          ${witnessId},
          ${sequence},
          ${headSha256},
          ${generation},
          ${keysetSha256},
          ${stateSha256}
        ) as result`
      );
      const result = rows?.[0]?.result;
      if (!result || typeof result !== 'object') {
        return json({ status: 'unavailable', reasonCode: 'witness-result-invalid' }, 503);
      }
      const status =
        result.status === 'denied' ? 401 :
        result.status === 'invalid' ? 400 :
        result.status === 'rejected' ? 409 :
        result.status === 'unavailable' ? 503 :
        200;
      return json(result, status);
    }

    return json({ status: 'invalid', reasonCode: 'method-not-allowed' }, 405);
  } catch {
    return json({ status: 'unavailable', reasonCode: 'witness-dependency-unavailable' }, 503);
  }
});
