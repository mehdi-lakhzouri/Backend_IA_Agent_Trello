"""Validation utilitaire pour les routes."""
from __future__ import annotations
from typing import Iterable, Dict, Any, Tuple, List


def require_json(data: Dict[str, Any] | None, required: Iterable[str]) -> Tuple[bool, List[str]]:
    if data is None:
        return False, list(required)
    missing = [f for f in required if not data.get(f)]
    return len(missing) == 0, missing
