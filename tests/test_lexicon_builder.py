from src.lexicon_builder import LexiconBuilder


def test_lexicon_builder_returns_review_queue_policy():
    builder = LexiconBuilder(language="fr", max_features=100)
    notes = [
        "Client recherche sac weekend en toile et cuir noir.",
        "Demande sac weekend avec format travel et style business.",
        "Preference pour sac weekend compact et leger.",
        "Besoin d'un sac pour weekend et voyage.",
    ]
    taxonomy = {
        "version": "2.2",
        "product_keywords": {
            "leather_goods": ["sac", "bag"],
            "travel_luggage": ["valise", "travel"],
        },
    }

    payload = builder.build_review_queue(notes, taxonomy, min_occurrences=1, limit=20)
    assert payload["policy"]["auto_merge"] is False
    assert payload["policy"]["review_required"] is True
    assert payload["policy"]["target_file_unchanged"] == "config/taxonomy_v2.2.json"
    assert "review_queue" in payload
    assert isinstance(payload["review_queue"], list)
