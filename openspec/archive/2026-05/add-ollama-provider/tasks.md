# Tasks — add-ollama-provider

- [x] `OllamaProvider` with extract_draft + judge + refine
- [x] httpx POST to /api/chat with `format: json`
- [x] CLI provider factory `ollama` branch
- [x] config/default.yml ollama block (host/model/timeout_s)
- [x] Tests: happy/sad paths for all three methods, unreachable server, HTTP error, unparseable content, request shape
- [x] `/review` ran, fixes applied:
  - Promoted `_extract_json_object` from `claude_code.py` to public `extract_json_object` in `providers/_judge.py`
  - Added cross-prompt consistency test (axes + severities present in every judge prompt)
  - Fixed mypy strict on `host` arg in `_build_provider`
- [x] `/security-review` — clean, no findings
