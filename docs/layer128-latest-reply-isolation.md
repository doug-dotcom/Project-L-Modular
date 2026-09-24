# Layer 128 — latest-reply playback isolation

Saved-answer review previously used the shared chat renderer, which also updates the text read by the main speaker button. Checking older answers could silently replace the latest chat reply with an old answer or a review notice.

The renderer now has an explicit option to leave the latest-reply text unchanged. Saved-answer review uses it for every displayed result. Normal chat replies retain existing playback behaviour. Review and refresh remain silent and do not select an older answer for playback.

Validation runs the actual shared renderer within the review harness, covering ready, stale, rejected, unavailable and failed retrievals; refresh; no prior reply; and subsequent live replies. Phone visual testing remains outstanding.
