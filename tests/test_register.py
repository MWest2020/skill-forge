"""Tests for forge register — change add-skill-register."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from typer.testing import CliRunner

from skill_forge.cli import app
from skill_forge.models import Skill, SourceRef
from skill_forge.register import build_register, write_register
from skill_forge.storage import filesystem as fs

runner = CliRunner()


def _skill(name: str) -> Skill:
    return Skill(
        name=name,
        description=f"Use when {name}.  Extra   spaces.",
        version=1,
        sources=[SourceRef(id="src-abc123")],
        created=date(2026, 5, 24),
        body="# Body\n",
    )


def test_only_live_skills_sorted(tmp_path: Path) -> None:
    fs.write_skill(tmp_path, _skill("beta"), draft=False)
    fs.write_skill(tmp_path, _skill("alpha"), draft=False)
    fs.write_skill(tmp_path, _skill("draftskill"), draft=True)

    m = build_register(tmp_path)
    slugs = [e["slug"] for e in m["skills"]]
    assert slugs == ["alpha", "beta"]  # live only, alfabetisch
    assert "draftskill" not in slugs
    # one-line description: whitespace platgeslagen
    assert m["skills"][0]["description"] == "Use when alpha. Extra spaces."


def test_write_and_reload(tmp_path: Path) -> None:
    fs.write_skill(tmp_path, _skill("gamma"), draft=False)
    out = tmp_path / "register.yml"
    n = write_register(tmp_path, out)
    assert n == 1
    loaded = yaml.safe_load(out.read_text())
    assert loaded["generator"] == "skill-forge"
    assert loaded["skills"][0]["slug"] == "gamma"


def test_cli_register(tmp_path: Path) -> None:
    fs.write_skill(tmp_path, _skill("delta"), draft=False)
    res = runner.invoke(app, ["register", "--root", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert "1 live skills" in res.output
    assert (tmp_path / "register.yml").is_file()
