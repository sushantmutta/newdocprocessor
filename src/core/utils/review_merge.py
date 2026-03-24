from __future__ import annotations

from copy import deepcopy
from typing import Any


def _deep_merge(base: Any, patch: Any) -> Any:
    if isinstance(base, dict) and isinstance(patch, dict):
        out = deepcopy(base)
        for key, value in patch.items():
            out[key] = _deep_merge(out.get(key), value)
        return out
    if isinstance(base, list) and isinstance(patch, list):
        # Patch list is treated as authoritative replacement for that field.
        return deepcopy(patch)
    return deepcopy(patch)


def merge_override(original: dict | None, repaired: dict | None, human_patch: dict | None) -> dict:
    """Merge partial human overrides over repaired data.

    Merge order:
    1) Start with original for baseline field preservation.
    2) Overlay repaired data.
    3) Overlay human patch only for edited fields.
    """
    baseline = deepcopy(original or {})
    merged = _deep_merge(baseline, repaired or {})
    return _deep_merge(merged, human_patch or {})
