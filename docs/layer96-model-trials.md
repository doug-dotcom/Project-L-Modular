# Layer 96 model trials

The operator runner compares candidate models on nine public synthetic fixtures,
separately reporting conversation, recall and reasoning. It does not exercise
production retrieval or the entire chat pipeline. It does not change routes,
write personal memory, or choose a winner.

Plan without making model calls:

```sh
python -m scripts.run_model_trials --models MODEL_A MODEL_B --repeats 2
```

In an authorised runtime with the existing `OPENAI_API_KEY`, add `--run` to
execute the plan. There may be one to three distinct candidates and one to three
repeats: at most 81 calls. Each request permits up to 2,048 output tokens; the
client has a 45-second timeout with no automatic retries. A five-minute overall
deadline is checked between calls. A provider error stops that candidate; other
candidates can continue. Skipped and failed cases remain in the report.

Outputs include the case-set fingerprint, requested and returned model IDs,
answers, available provider receipts, timings and recorded costs. Costs retain
their original currency and estimation basis. Missing prices remain unpriced.
Review the returned-model identity if a provider resolves an alias to a snapshot.

Conversation responses always require human review against the attached rubric.
Objective cases only report narrow fixture checks, not whole-answer correctness.
A zero command exit code means execution finished without failed/unexecuted
cases; it does not mean human review passed. Promotion eligibility is always
false: this report is not consumed by the production route selector.

Before choosing a model, execute repeated trials, review complete answers and
identity differences, and add a private held-out set with production retrieval.
Compare quality alongside latency and recorded cost. Never treat the mocked
regression tests as live model scores.
