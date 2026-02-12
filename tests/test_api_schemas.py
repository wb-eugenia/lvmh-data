import os
import sys

sys.path.append(os.getcwd())

from api.schemas import NoteInput, ParityProjection


def test_note_input_accepts_extended_languages():
    text = "Ceci est une note de test suffisante."
    for raw, expected in [
        ("FR", "FR"),
        ("EN", "EN"),
        ("IT", "IT"),
        ("ES", "ES"),
        ("DE", "DE"),
        ("en-us", "EN"),
        ("de-de", "DE"),
        ("uk", "EN"),
    ]:
        parsed = NoteInput(text=text, language=raw)
        assert parsed.language == expected


def test_note_input_unknown_language_falls_back_to_fr():
    parsed = NoteInput(text="Ceci est une autre note de test.", language="PT")
    assert parsed.language == "FR"


def test_parity_projection_normalizes_bool_and_tags():
    projection = ParityProjection(
        tier="2",
        rgpd_contains_sensitive="false",
        tags=[" Capucines ", "capucines", "LEATHER_GOODS"],
    )
    assert projection.tier == 2
    assert projection.rgpd_contains_sensitive is False
    assert projection.tags == ["Capucines", "LEATHER_GOODS"]


def test_parity_projection_handles_empty_values():
    projection = ParityProjection(
        tier="invalid",
        rgpd_contains_sensitive="",
        tags=" , ,  ",
    )
    assert projection.tier == 1
    assert projection.rgpd_contains_sensitive is False
    assert projection.tags == []
