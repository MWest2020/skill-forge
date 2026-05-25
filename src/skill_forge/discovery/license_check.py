"""Classify a source URL's license into permissive/copyleft/restrictive/forbidden.

GitHub repos use the SPDX field. Arbitrary URLs use an HTML heuristic.
"""

from __future__ import annotations

import re

# Mapping from SPDX/license-key prefixes to our four buckets.
_PERMISSIVE = {
    "MIT", "ISC", "BSD-2-CLAUSE", "BSD-3-CLAUSE", "APACHE-2.0",
    "CC0-1.0", "CC-BY-4.0", "CC-BY-3.0", "UNLICENSE", "ZLIB",
    "MIT-0", "0BSD",
}
_COPYLEFT = {
    "GPL-2.0", "GPL-3.0", "LGPL-2.1", "LGPL-3.0", "AGPL-3.0",
    "MPL-2.0", "EPL-2.0", "CDDL-1.0", "CC-BY-SA-4.0", "CC-BY-SA-3.0",
    "EUPL-1.2", "EUPL-1.1",
}
_RESTRICTIVE = {
    "CC-BY-NC-4.0", "CC-BY-NC-SA-4.0", "CC-BY-ND-4.0", "BUSL-1.1",
}


def classify_spdx(spdx: str | None) -> str:
    """Bucket a SPDX identifier (or None) into our four classes."""
    if not spdx:
        return "forbidden"
    norm = spdx.upper().replace("LICENSE-", "").strip()
    # GitHub uses license.key like "mit", "apache-2.0", "other" — uppercase first.
    if norm in _PERMISSIVE:
        return "permissive"
    if norm in _COPYLEFT:
        return "copyleft"
    if norm in _RESTRICTIVE:
        return "restrictive"
    if norm in {"OTHER", "NOASSERTION", "NONE", ""}:
        return "forbidden"
    return "forbidden"  # unknown ID — fail closed


_HTML_LICENSE_HINTS = re.compile(
    r"(?:rel=[\"']license[\"']|<meta\s+name=[\"']license[\"']|"
    r"License\s*:\s*([A-Za-z0-9\.\-+]+))",
    re.IGNORECASE,
)
_SPDX_IN_HTML = re.compile(
    r"\b(MIT|Apache-2\.0|BSD-[23]-Clause|GPL-[23]\.0|LGPL-[23]\.[01]|"
    r"AGPL-3\.0|MPL-2\.0|EUPL-1\.[12]|CC-BY(?:-NC)?(?:-SA)?-[34]\.0|"
    r"ISC|Unlicense|CC0-1\.0)\b",
    re.IGNORECASE,
)


def classify_html(body: str) -> str:
    """Scan a small HTML body for license hints. Fail closed when nothing found."""
    if not body or not _HTML_LICENSE_HINTS.search(body):
        # Try direct SPDX mention as fallback before giving up.
        match = _SPDX_IN_HTML.search(body or "")
        if match:
            return classify_spdx(match.group(1))
        return "forbidden"
    match = _SPDX_IN_HTML.search(body)
    if match:
        return classify_spdx(match.group(1))
    return "forbidden"
