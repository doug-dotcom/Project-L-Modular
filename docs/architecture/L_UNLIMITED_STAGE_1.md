# L Unlimited — Stage 1: live evaluation and evidence checks

## Problem

Observed conversation tests showed useful recall and reasoning, but a quotation
could be attached to the wrong record. Numeric IDs collide across tables. A
synthetic cognitive benchmark alone did not inspect the actual final answer.

## Delivered behaviour

Rhee now carries an evidence array alongside its existing context. Each entry is
created from an actually selected raw or long-term record, with `table:id`, role,
timestamp and precisely the excerpt shown to the model. It is not reconstructed
by interpreting arbitrary text inside a memory. Concurrent requests have separate
arrays; no shared mutable evidence registry is introduced.

Personal-memory requests and explicit evidence requests use a structured final
answer through the existing model adapter. The server renders the answer after
checking source membership, exact quotation attribution (allowing whitespace and
typographic quote differences), missing references and assistant-only support.
An invalid section is withheld; valid sections remain. Invalid JSON is withheld
instead of bypassing the gate. This happens before assistant-memory writes,
reflection and speech. No new credentials, model selection or database migration
is required.

Every checked `/chat` response includes `cognition.evidence_evaluation`: model,
request ID, timestamp, source count, per-block issues, qualified source references,
quote hashes and draft/reply hashes. No whole private draft is put in the receipt.
The ordinary ten-minute chat-result cache carries this with the existing payload;
durable job/receipt storage is Stage 2, not claimed here.

`GET /cognition/evaluation` describes these checks; it does not claim a score.
The existing `/cognition/benchmark` remains the separate deterministic Phase 7 suite.

## Operator model trials

From the repository with the application's existing environment configured:

```bash
python -m scripts.run_live_evaluation --repeats 2
```

This executes ten model requests (five cases twice) through the production answer
contract and evaluator. Each request is capped at 1,000 output tokens. It tests
table/ID collisions, documented change, unknown facts, prior-answer contamination,
and Brisbane chronology with synthetic evidence. It never reads or writes personal
memory, imports the server, runs services or promotes lessons. JSON results include
individual checks, timing, model ID, replies and failures. Exit code 1 means at
least one case failed. The local CI tests use fake adapters, not live model calls.

## Limits to preserve in reporting

- Quote presence does not establish that a claim follows from the quote. Semantic
  accuracy is explicitly `not_independently_verified`.
- The model assigns fact/inference/conversation labels. Misclassification can
  escape citation requirements; this is not a complete factuality firewall.
- USER role means a user-supplied record, which may itself contain an AI-written
  report. It is not proof of original human authorship or external truth.
- Raw and long-term retrieval excerpts are supported. Identity/learning context
  without qualified retrieval receipts cannot be invented into a citation.
- Only text actually supplied can validate a quote; omitted report endings require
  better retrieval, not automatic approval of the full unseen source.
- No-citation answers are `no_citations_to_check`, never counted as factual passes.
- The bounded model suite uses explicit expected sources, block kinds and answer
  terms. These are transparent narrow checks, not a general semantic grader.
- No claim of complete recall, production retrieval accuracy, automatic correction
  persistence, voice quality or restart recovery follows from passing this suite.

## Acceptance and rollback

Run `python -m pytest -q tests/test_evidence_evaluation.py` plus the existing active
memory/cognitive suites. Coverage includes wrong-table references, absent IDs,
invented quotes, missing support, self-confirmation, source-text spoofing,
truncation, partial survival and validation-before-save integration.

After deployment, confirm the manifest and health endpoints, then inspect an
actual memory answer's receipt and supporting passage. Compare with the recorded
pre-change baseline; do not present a small sample as system-wide improvement.
Rollback is a normal revert of this Stage 1 commit; no schema rollback is needed.
