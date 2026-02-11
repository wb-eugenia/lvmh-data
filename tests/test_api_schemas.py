import os
import sys

sys.path.append(os.getcwd())

from api.schemas import NoteInput


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
