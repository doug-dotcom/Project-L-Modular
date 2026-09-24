# Layer 116 — Check saved answers from the app

The + menu now offers **Check saved answers**. It runs the Layer 115 combined
recovery report on demand and displays a plain-language result in the chat,
with task, recoverable-answer and unfinished-task counts.

Ready, legacy, unfinished, attention-needed, incomplete and empty results have
distinct copy. The card explains the browser recovery link and scan boundary,
and distinguishes storage/recovery checks from answer accuracy. A missing local
recovery link produces a local explanation without creating a new link or
querying the server.

The check is GET-only and uses the existing account-authorised fetch wrapper
with the browser's recovery token. It is bounded to 30 seconds, including body
reads. Repeat clicks while pending are ignored. Retrying replaces the old card,
and failures remove any previous success message. Account locking or changing
clears the card and prevents late responses from restoring it.

Only fixed text and validated numeric counts reach the card. Unknown or
inconsistent reports become an unavailable result. Raw backend error text,
identifiers, tokens and findings are never displayed. Keyboard focus moves to
the result card and its status is announced to assistive technology.

No task replay, repair, model call or memory write is added. The existing
Saved answers action still retrieves answers separately. Regression coverage
exercises all six outcomes, malformed responses, no-link behaviour, retries,
duplicate clicks and account changes.
