import builtins
from typing import List, Tuple

import pytest

from config.production import settings
from src.tier1_rules import Tier1RulesEngine


def _build_engine(engine_name: str) -> Tier1RulesEngine:
    previous = settings.tier1_match_engine
    settings.tier1_match_engine = engine_name
    try:
        return Tier1RulesEngine()
    finally:
        settings.tier1_match_engine = previous


@pytest.mark.parametrize(
    "text",
    [
        "Je cherche un sac et une ceinture pour un cadeau.",
        "Client seeks leather bag and belt for a gift.",
        "Cliente cerca borsa weekend e cintura.",
        "Kundin sucht Tasche und Guertel als Geschenk.",
        "Client cherche sac à main noir.",
    ],
)
def test_aho_matches_regex_on_multilingual_notes(text: str):
    pytest.importorskip("ahocorasick")

    regex_engine = _build_engine("regex")
    aho_engine = _build_engine("aho")
    if aho_engine.match_engine != "aho":
        pytest.skip("Aho engine unavailable at runtime; fallback in effect.")

    regex_tags = set(regex_engine.extract_taxonomy_tags(text))
    aho_tags = set(aho_engine.extract_taxonomy_tags(text))

    assert regex_tags == aho_tags


def test_aho_word_boundaries_prevent_embedded_partial_matches():
    pytest.importorskip("ahocorasick")
    aho_engine = _build_engine("aho")
    if aho_engine.match_engine != "aho":
        pytest.skip("Aho engine unavailable at runtime; fallback in effect.")

    candidate: Tuple[str, str] | None = None
    for alias, tag in aho_engine.keyword_map.items():
        normalized = str(alias).strip().lower()
        if normalized.isalpha() and len(normalized) >= 5:
            candidate = (normalized, tag)
            break

    if not candidate:
        pytest.skip("No suitable keyword found to validate embedded-word boundary.")

    alias, tag = candidate
    text = f"xx{alias}yy"
    tags = set(aho_engine.extract_taxonomy_tags(text))

    assert tag not in tags


def test_aho_import_failure_falls_back_to_regex(monkeypatch):
    previous = settings.tier1_match_engine
    settings.tier1_match_engine = "aho"
    original_import = builtins.__import__

    def raising_import(name, *args, **kwargs):
        if name == "ahocorasick":
            raise ImportError("forced missing ahocorasick for fallback test")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", raising_import)
    try:
        engine = Tier1RulesEngine()
    finally:
        settings.tier1_match_engine = previous

    assert engine.match_engine == "regex"

