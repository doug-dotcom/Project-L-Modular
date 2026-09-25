# Layer 154 — Validate file-question inputs before sending

The file panel checks that a page is a whole number within the current document and the server's 30-page maximum. It also checks the trimmed question against the server's 4,000-character limit, counting Unicode code points so emoji do not consume two characters unnecessarily.

Invalid inputs display correction guidance before touching recovery storage, disabling Ask, clearing the displayed answer, submitting or polling. The draft, preview, previous answer and pending recovery marker remain available. An explicit retry after correcting the input follows the existing submission and recovery flow. Server validation remains authoritative.

Fifteen scenarios cover blank, zero, negative, fractional, non-numeric and out-of-range pages; server page limits; oversized questions; valid page boundaries; maximum-length questions; Unicode and surrounding whitespace. Full CI and live checks accompany the release. Phone visual testing remains outstanding.
