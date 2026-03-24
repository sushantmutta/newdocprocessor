from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

from config.settings import get_settings


@dataclass
class KnowledgeStore:
    drugs: dict[str, dict]
    lab_tests: dict[str, dict]
    drug_aliases: dict[str, str]


def _normalize(value: str) -> str:
    value = (value or "").lower().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _load_json(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
        return data if isinstance(data, list) else []


def _load_aliases(path: Path) -> dict[str, str]:
    aliases: dict[str, str] = {}
    if not path.exists():
        return aliases
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            alias = _normalize(row.get("alias", ""))
            canonical = _normalize(row.get("canonical", ""))
            if alias and canonical:
                aliases[alias] = canonical
    return aliases


def build_store() -> KnowledgeStore:
    base = get_settings().processing.knowledge_dir
    base.mkdir(parents=True, exist_ok=True)

    drugs_raw = _load_json(base / "drugs.json")
    labs_raw = _load_json(base / "lab_tests.json")
    aliases = _load_aliases(base / "drug_aliases.csv")

    drugs = {_normalize(item.get("name", "")): item for item in drugs_raw if item.get("name")}
    lab_tests = {_normalize(item.get("name", "")): item for item in labs_raw if item.get("name")}
    return KnowledgeStore(drugs=drugs, lab_tests=lab_tests, drug_aliases=aliases)


def exact_lookup(value: str, category: str, store: KnowledgeStore) -> dict | None:
    key = _normalize(value)
    if not key:
        return None
    if category == "drug":
        mapped = store.drug_aliases.get(key, key)
        return store.drugs.get(mapped)
    if category == "lab_test":
        return store.lab_tests.get(key)
    return None
