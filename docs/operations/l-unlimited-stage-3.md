# L Unlimited Stage 3: modern models and measured routing

Stage 3 follows live evidence evaluation (PR 24) and durable answers (PR 25).
The inspected baseline was GPT-4o-mini on Chat Completions, not Astra.

The model factory selects Responses for reasoning models and preserves the
configured legacy model. Responses translation includes text, image input and
JSON/strict-schema output. Unsupported tools, audio/video and streaming are not
advertised as implemented. Temperature is omitted for reasoning models. L owns
conversation state; provider storage is disabled.

Answer and RIKE receipts contain model, endpoint, completion state, latency,
token usage and a dated USD standard-text cost estimate when pricing is known.
Unknown costs remain null. Estimates exclude alternate service tiers, long
context premiums and provider cache-write charges; they are not invoices.
Refusals, unfinished answers and unsupported output cannot become completed
assistant memories. Durable tasks retain the failure receipt without retrying
the cognition or external actions.

## Trial and promotion

Run `python -m scripts.compare_l_models --output /tmp/l-model-trials.json`
inside the existing service environment. This reads its existing OpenAI key;
the key never appears in output. The operator command has no database or tool
access and tests only synthetic evidence using L's production evidence contract.
It compares the configured baseline, Terra, Sol and Astra: five cases repeated
twice, 4096 output tokens per request, 45-second timeout, no SDK retries. Access
denials stop that candidate. Model requests run in four independent threads.

Review quality and completion first, then latency and estimated cost. Configure
`configs/model_routes.json` only with an actual full evaluation report and
`enabled: true`. The router requires all ten cases to pass, completed receipts
from that exact model and API, a maximum 60-second per-case duration and results
less than 30 days old. Invalid/stale results retain the configured baseline.
There is no automatic promotion or fallback after failed generation.

This suite measures bounded evidence answers. Only `l_recall_response` is eligible
for its route. RIKE, reports, image understanding and conversation retain the
configured baseline until separately evaluated. Citation checks and answer-term
checks do not establish semantic truth or certify live retrieval.

`L_MODEL_API` selects `auto`, `responses` or `chat_completions` for the baseline.
`L_REASONING_EFFORT` defaults to `low`. `L_MODEL_ROUTES_PATH` can select a reviewed
operator route file. These are server configuration, never chat-controlled fields.

Rollback: disable the route file or revert the stage commit. No schema migration
is required; Stage 2 saves the receipts within its existing answer JSON.

## Provider references checked 5 September 2026

- https://developers.openai.com/api/docs/guides/migrate-to-responses
- https://developers.openai.com/api/docs/models/gpt-6-astra
- https://developers.openai.com/api/docs/models/gpt-5.6-sol
- https://developers.openai.com/api/docs/models/gpt-5.6-terra
- https://developers.openai.com/api/docs/models/gpt-4o-mini
