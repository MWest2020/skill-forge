"""Tests for `forge extract` — change #2."""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from skill_forge.cli import _run_extract, app
from skill_forge.providers.base import DistilledDraft, LLMProviderError
from skill_forge.storage import filesystem as fs
from skill_forge.storage.filesystem import free_slug

from .fakes import FakeProvider

runner = CliRunner()


class _FakeProvider(FakeProvider):
    def __init__(self, draft: DistilledDraft) -> None:
        self.draft = draft

    def extract_draft(self, *, source_url: str, source_text: str) -> DistilledDraft:
        return self.draft


def _draft(name: str = "smoke-draft") -> DistilledDraft:
    return DistilledDraft(
        name=name,
        description="Use this skill when X.",
        body="## When to use\nNever.\n## Procedure\n1. Read.\n## Failure modes\nNone.\n",
    )


def _write_fixture_html(tmp_path: Path) -> Path:
    page = tmp_path / "sample.html"
    page.write_text(
        "<html><body><h1>Title</h1><p>Body content.</p></body></html>",
        encoding="utf-8",
    )
    return page


def test_run_extract_writes_draft_and_sources(tmp_path: Path) -> None:
    page = _write_fixture_html(tmp_path)
    provider = _FakeProvider(_draft())

    _run_extract(
        f"file://{page}",
        root=tmp_path,
        follow_next=False,
        max_pages=10,
        provider=provider,
    )

    skill_path = tmp_path / "skills" / "_draft" / "smoke-draft" / "SKILL.md"
    sources_path = tmp_path / "sources" / "smoke-draft.yml"
    assert skill_path.is_file()
    assert sources_path.is_file()

    loaded = fs.read_skill(tmp_path, "smoke-draft")
    assert loaded.name == "smoke-draft"
    assert loaded.judge_score is None
    assert len(loaded.sources) == 1

    loaded_sources = fs.read_sources(tmp_path, "smoke-draft")
    assert loaded_sources.sources[0].license == "unknown"
    assert loaded_sources.sources[0].contribution == "single page"


def test_run_extract_auto_suffixes_on_collision(tmp_path: Path) -> None:
    page = _write_fixture_html(tmp_path)
    provider = _FakeProvider(_draft())

    _run_extract(
        f"file://{page}",
        root=tmp_path,
        follow_next=False,
        max_pages=10,
        provider=provider,
    )
    _run_extract(
        f"file://{page}",
        root=tmp_path,
        follow_next=False,
        max_pages=10,
        provider=provider,
    )

    assert (tmp_path / "skills" / "_draft" / "smoke-draft" / "SKILL.md").is_file()
    assert (tmp_path / "skills" / "_draft" / "smoke-draft-2" / "SKILL.md").is_file()
    assert (tmp_path / "sources" / "smoke-draft-2.yml").is_file()


def test_run_extract_fetch_error_exits_1(tmp_path: Path) -> None:
    provider = _FakeProvider(_draft())
    missing = tmp_path / "does-not-exist.html"
    with pytest.raises(typer.Exit) as exc:
        _run_extract(
            f"file://{missing}",
            root=tmp_path,
            follow_next=False,
            max_pages=10,
            provider=provider,
        )
    assert exc.value.exit_code == 1


def test_run_extract_provider_error_exits_3(tmp_path: Path) -> None:
    class _Boom(FakeProvider):
        def extract_draft(self, *, source_url: str, source_text: str) -> DistilledDraft:
            raise LLMProviderError("upstream broken")

    page = _write_fixture_html(tmp_path)
    with pytest.raises(typer.Exit) as exc:
        _run_extract(
            f"file://{page}",
            root=tmp_path,
            follow_next=False,
            max_pages=10,
            provider=_Boom(),
        )
    assert exc.value.exit_code == 3


def _write_config(tmp_path: Path, provider: str) -> None:
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "default.yml").write_text(f"providers:\n  extract: {provider}\n", encoding="utf-8")


def test_extract_cli_missing_api_key_exits_2_when_anthropic_selected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path, "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = runner.invoke(app, ["extract", "file:///nonexistent", "--root", str(tmp_path)])
    assert result.exit_code == 2
    assert "ANTHROPIC_API_KEY" in (result.stderr or result.output)


def test_extract_cli_skips_api_key_guard_for_claude_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path, "claude_code")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = runner.invoke(app, ["extract", "file:///nonexistent", "--root", str(tmp_path)])
    # Should NOT exit 2 — should reach the fetcher and exit 1 on missing file.
    assert result.exit_code == 1
    assert "ANTHROPIC_API_KEY" not in (result.stderr or result.output)


def test_extract_cli_unknown_provider_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path, "magic-mystery-llm")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")  # so we pass the guard
    result = runner.invoke(app, ["extract", "file:///nonexistent", "--root", str(tmp_path)])
    assert result.exit_code == 2
    assert "unknown provider" in (result.stderr or result.output)


def test_free_slug_finds_first_open_suffix(tmp_path: Path) -> None:
    assert free_slug(tmp_path, "foo") == "foo"

    (tmp_path / "skills" / "foo").mkdir(parents=True)
    (tmp_path / "skills" / "foo" / "SKILL.md").write_text("---\n---\n")
    assert free_slug(tmp_path, "foo") == "foo-2"

    (tmp_path / "skills" / "_draft" / "foo-2").mkdir(parents=True)
    (tmp_path / "skills" / "_draft" / "foo-2" / "SKILL.md").write_text("---\n---\n")
    assert free_slug(tmp_path, "foo") == "foo-3"
