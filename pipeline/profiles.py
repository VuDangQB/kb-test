"""Ticker profiles: entity map (with listing dates) and point-in-time financials."""

import unicodedata
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml

PROFILE_DIR = Path(__file__).resolve().parent.parent / "profiles"


def norm(text: str) -> str:
    return unicodedata.normalize("NFC", text).casefold().strip()


@dataclass
class Entity:
    name: str
    aliases: list[str] = field(default_factory=list)
    listed_ticker: str | None = None
    listed_since: date | None = None
    core: bool = True
    kind: str = "subsidiary"  # subsidiary | shareholder | associate
    ownership: list[dict] = field(default_factory=list)

    def names(self) -> set[str]:
        return {norm(self.name), *(norm(a) for a in self.aliases)} | (
            {norm(self.listed_ticker)} if self.listed_ticker else set())

    def is_listed_on(self, day: date) -> bool:
        return bool(self.listed_ticker and self.listed_since and self.listed_since <= day)


@dataclass
class Profile:
    ticker: str
    name: str
    aliases: list[str]
    entities: list[Entity]
    financials: list[dict]
    sector_variables: list[str]
    raw_yaml: str

    def find_entity(self, name: str) -> Entity | None:
        key = norm(name)
        if not key:
            return None
        for ent in self.entities:
            if key in ent.names():
                return ent
        return None

    def is_self(self, name: str) -> bool:
        return norm(name) in {norm(self.ticker), norm(self.name), *(norm(a) for a in self.aliases)}

    def financials_at(self, day: date) -> dict:
        """Latest financial snapshot with as_of <= day (G-8). Empty if none."""
        rows = [r for r in self.financials if r.get("as_of") and r["as_of"] <= day]
        return max(rows, key=lambda r: r["as_of"]) if rows else {}


def _load(path: Path) -> Profile:
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    entities = [Entity(**e) for e in data.get("entities", [])]
    return Profile(
        ticker=data["ticker"], name=data["name"], aliases=data.get("aliases", []),
        entities=entities, financials=data.get("financials", []) or [],
        sector_variables=data.get("sector_variables", []), raw_yaml=text,
    )


@lru_cache
def load_profiles(directory: str = str(PROFILE_DIR)) -> dict[str, Profile]:
    profiles = {}
    for path in sorted(Path(directory).glob("*.yaml")):
        p = _load(path)
        profiles[p.ticker] = p
    return profiles
