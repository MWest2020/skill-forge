# Tasks — add --source-url to forge import

- [x] 1.1 `import_file(..., source_url=None, license=None)` — thread to normalize + `_build_source`
- [x] 1.2 CLI: `--source-url` / `--license` on `forge import`
- [x] 1.3 Tests: with url → frontmatter url + `## Source` + Source record url/license; without → `local-author:` unchanged
- [x] 1.4 Gate (pytest/ruff/mypy) + archive
