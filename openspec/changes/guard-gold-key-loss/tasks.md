# Tasks — guard against silent gold-key loss

- [x] 1.1 `_warn_gold_key(home)` in trust.py: detect mint-vs-load and volatile path, emit stderr warnings
- [x] 1.2 Call it in `forge gold` before `get_or_create`
- [x] 1.3 Tests: mint → "NEW gold identity"; volatile path → "volatile"; existing key on persistent path → silent
- [x] 1.4 Gate (pytest/ruff/mypy) + archive
