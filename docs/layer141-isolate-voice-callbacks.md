# Layer 141 — isolate optional voice callbacks

Typed chat continues if the voice helper’s draft-saving callback throws. Once an answer is delivered, a failed voice reply callback no longer enters the network-recovery error path or adds a misleading waiting error. This applies to both normal delivery and recovery after an uncertain acknowledgement.

The voice canSend guard still runs before submission. Request persistence, single submission, answer recovery and pending-record cleanup retain their existing behaviour. This change protects text chat from optional callback failures; it does not repair speech playback or guarantee that a failing voice helper persisted its own draft.

Validation injects draft, reply, combined and uncertain-acknowledgement callback failures and checks a single submission, one visible answer, successful cleanup and no misleading error. Phone visual testing remains outstanding.
