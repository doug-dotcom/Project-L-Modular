# Project L production-tree hygiene — 30 September 2026

Project L's historical snapshots are intentionally preserved, but they are not runtime dependencies.

## Preservation

The complete pre-pruning repository tree is preserved on branch `archive-full-tree-20260930`, rooted at commit `654be28c3022923a2cc0b08074dc7be7c4f89d6d`. The same objects also remain in Git history.

## Production-tree exclusions

The production branch removes only these historical archive trees:

- `FULL_BACKUPS/`
- `_FULL_BACKUPS/`
- `_LOCKED_RELEASE/`
- `LOCKED_RELEASES/`
- `MANTLE/`
- `backups/`
- `_smart_backups/`
- `api/Backups/`

Runtime code, tests, current memory data, migrations, configuration, docs and active application assets remain in `main`.

The purpose is to stop historical archives from dominating Railway source snapshots while retaining recoverability through Git history and the dedicated archive branch.
