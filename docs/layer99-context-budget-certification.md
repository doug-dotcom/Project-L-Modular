# Layer 99 — Context-budget quality certification

Layer 99 validates Layer 98's adaptive model-facing cognition reduction without
pretending that smaller prompts are automatically better.

It adds two distinct forms of evidence:

1. **Production-path regression** — the real `/chat` handler is exercised with a
   fixture model and a cognition packet containing an inactive marker. The marker
   must remain in the full runtime packet but must not enter the model prompt.
2. **Bounded full-vs-budgeted provider trials** — public synthetic conversation,
   recall and reasoning fixtures can be sent to the same model twice: once with
   the full cognitive packet and once with Layer 98's budgeted packet.

## Safety and privacy

The provider trial suite:

- uses public synthetic fixtures only;
- never reads Doug's personal memory;
- never writes memory;
- never changes model routes;
- never promotes a model or context strategy;
- exposes only bounded provider receipts and synthetic answers.

The full and budgeted variants receive the same user request and the same
synthetic Rhee evidence. Only the cognitive-packet representation differs.

## What can pass automatically

Recall and reasoning fixtures have narrow objective checks, such as an exact
synthetic source/code, a constrained departure time, or a causal-boundary
boolean. A pair receives `objective_parity` only when **both** the full and
budgeted variants pass the same fixture check.

This does not certify the entire wording or reasoning quality of either answer.

## What requires human review

Conversation quality is not reduced to a fluency score. Both variants must
produce usable replies, after which the pair remains `review_required` against
a written rubric.

A trial report therefore cannot automatically mark Layer 98 "better" or select a
winner. Even when all objective pairs match, the overall certification remains
`review_required` until conversation outputs are reviewed.

## Running the suite

Planning mode makes no provider calls:

```sh
python -m scripts.run_context_budget_trials --models MODEL_A --repeats 1
```

Authorised execution:

```sh
python -m scripts.run_context_budget_trials --models MODEL_A --repeats 1 --run
```

The maximum supported plan is two models × two repeats × four cases × two
variants = **32 calls**. The default single-model/single-repeat plan is **8
calls**.

Execution requires the existing `OPENAI_API_KEY`. Provider retries are disabled
and the client timeout is 45 seconds. Any provider failure stops that candidate;
unexecuted rows stay visible rather than disappearing from the report.

## Acceptance boundary

Layer 99 can establish:

- that production prompt composition actually uses the Layer 98 budget;
- that inactive cognition is excluded from the model-facing prompt;
- that synthetic Rhee evidence is unchanged;
- whether objective synthetic answers remain equivalent under full and budgeted
  cognition; and
- which conversation pairs require human quality review.

It does **not** establish production-user quality, private-memory recall quality,
latency improvement, or phone UX quality. Those require separate live acceptance
using real authorised sessions and human review.
