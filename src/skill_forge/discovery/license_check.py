"""Classify a source URL's license into permissive/copyleft/restrictive/forbidden.

GitHub repos use the SPDX field. Arbitrary URLs use an HTML heuristic.
"""

from __future__ import annotations

import re

_PERMISSIVE = {
    "MIT", "ISC", "BSD-2-CLAUSE", "BSD-3-CLAUSE", "APACHE-2.0",
    "CC0-1.0", "CC-BY-4.0", "CC-BY-3.0", "UNLICENSE", "ZLIB",
    "MIT-0", "0BSD",
}
_COPYLEFT = {
    "GPL-2.0", "GPL-3.0", "LGPL-2.0", "LGPL-2.1", "LGPL-3.0",
    "AGPL-3.0", "MPL-1.1", "MPL-2.0", "EPL-1.0", "EPL-2.0",
    "CDDL-1.0", "CDDL-1.1", "CC-BY-SA-4.0", "CC-BY-SA-3.0",
    "EUPL-1.2", "EUPL-1.1",
}
_RESTRICTIVE = {
    "CC-BY-NC-4.0", "CC-BY-NC-SA-4.0", "CC-BY-ND-4.0", "BUSL-1.1",
}

# SPDX 3.x suffixes — strip before bucket lookup.
_SUFFIX_RE = re.compile(r"-(ONLY|OR-LATER)$")


def classify_spdx(spdx: str | None) -> str:
    """Bucket a SPDX identifier (or None) into our four classes."""
    if not spdx:
        return "forbidden"
    norm = _SUFFIX_RE.sub("", spdx.upper().replace("LICENSE-", "").strip())
    if norm in _PERMISSIVE:
        return "permissive"
    if norm in _COPYLEFT:
        return "copyleft"
    if norm in _RESTRICTIVE:
        return "restrictive"
    return "forbidden"  # unknown / "OTHER" / "NOASSERTION" — fail closed


_SPDX_IN_HTML = re.compile(
    r"\b(MIT|Apache-2\.0|BSD-[23]-Clause|GPL-[23]\.0|LGPL-[23]\.[01]|"
    r"AGPL-3\.0|MPL-[12]\.[01]|EUPL-1\.[12]|EPL-[12]\.0|CDDL-1\.[01]|"
    r"CC-BY(?:-NC)?(?:-SA)?-[34]\.0|ISC|Unlicense|CC0-1\.0|BUSL-1\.1)\b",
    re.IGNORECASE,
)


def classify_html(body: str) -> str:
    """Scan a small HTML body for an SPDX mention. Fail closed when absent."""
    match = _SPDX_IN_HTML.search(body or "")
    return classify_spdx(match.group(1)) if match else "forbidden"
