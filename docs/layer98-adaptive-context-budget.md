# Layer 98 — Adaptive cognitive context budget

Layer 98 separates Project L's full runtime cognition packet from the smaller
cognitive packet sent to the response model.

## Why

Ordinary conversation does not need every inactive cognitive subsystem repeated
inside the model prompt. The live prompt already renders the controller, working
memory and model interface separately, while the full cognitive packet previously
duplicated them and also carried inactive reasoning/pattern modules.

That increases context pressure without adding useful evidence.

## Behaviour

The new deterministic context-budget builder chooses one of three modes from the
existing cognitive controller:

- **lean** — ordinary conversation;
- **standard** — medium-complexity, memory, action or specialist work;
- **expanded** — evidence-backed, structured, longitudinal or high-difficulty work.

Every mode preserves runtime status, cognitive routing, guardrails and calibrated
confidence. Route-activated cognitive modules are preserved. Expanded mode also
retains RIKE, Mary, Quinn and confidence-evidence sections.

The controller plan, working memory, model interface and portability state are not
duplicated inside the cognitive packet because they are already rendered
separately or are audit-only.

## Safety boundary

Layer 98 does **not** edit, truncate or re-rank Rhee evidence. It does not change
the stored cognitive packet, memory, access control, model routing, provider
request integrity or publication verification.

If genuinely required cognitive context itself exceeds the target budget, the
receipt reports `required_context_exceeds_budget` rather than silently deleting
protected active reasoning.

The receipt contains section names and sizes only; it does not copy omitted
private values, messages, evidence or credentials.

## Budget targets

- lean: 12,000 characters
- standard: 24,000 characters
- expanded: 64,000 characters

These are deterministic model-facing context targets, not token counts or provider
limits.

## Validation

The Layer 98 regression suite checks:

1. inactive and separately-rendered sections are removed from lean context;
2. active RIKE/Mary/Quinn and memory reasoning survive expanded mode;
3. evidence-required responses automatically select expanded mode;
4. budget receipts do not contain omitted private values; and
5. the production server builds the budget before prompt composition and retains
   the receipt in the saved cognition packet.

Live-model quality, latency improvement and physical-phone acceptance remain
separate production checks.
