"""Bouw een manifest van de live (gepromoveerde) skills — de gezaghebbende
catalogus "welke skills bestaan" die consumenten (bv. de handbook-agent-registry)
tegen een `skills:`-claim kunnen valideren.

Spec: openspec/changes/add-skill-register/specs/skill-register/spec.md
"""

from __future__ import annotations

from pathlib import Path

import yaml

from skill_forge.storage.filesystem import read_skill_file

MANIFEST_VERSION = 1


def _one_line(text: str) -> str:
    """Eerste zin/regel van de description, whitespace platgeslagen."""
    return " ".join(text.split()).strip()


def build_register(root: Path) -> dict:
    """Manifest-dict van de live skills (alfabetisch op slug). Drafts
    (`skills/_draft/<slug>/`) blijven buiten: die zijn niet gepromoveerd."""
    skills_dir = root / "skills"
    entries = []
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        if skill_md.parent.name == "_draft":
            continue  # verdedigend; _draft heeft geen directe SKILL.md
        skill = read_skill_file(skill_md)
        entries.append({
            "slug": skill.name,
            "description": _one_line(skill.description),
            "origin": skill.origin,
        })
    entries.sort(key=lambda e: e["slug"])
    return {"version": MANIFEST_VERSION, "generator": "skill-forge", "skills": entries}


def write_register(root: Path, out: Path) -> int:
    """Schrijf het manifest naar `out`. Return het aantal skills."""
    manifest = build_register(root)
    out.write_text(
        "# Gegenereerd door `forge register` — niet met de hand bewerken.\n"
        + yaml.safe_dump(manifest, default_flow_style=False, sort_keys=False,
                         allow_unicode=True, width=1000)
    )
    return len(manifest["skills"])
