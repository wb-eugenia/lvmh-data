# LVMH Voice to Tag

Pipeline d'extraction automatique de tags structurés à partir de transcriptions vocales de Client Advisors pour LVMH Fashion & Leather Goods.

## 🎯 Objectif

Transformer les notes vocales non-structurées en intelligence business exploitable via une taxonomie de tags structurés pour:
- Enrichir le CRM client
- Personnaliser le clienteling
- Optimiser les campagnes marketing
- Détecter des insights business

## 🚀 Quick Start

```bash
# 1. Installer les dépendances
pip install -r requirements.txt

# 2. Configurer la clé API OpenAI
# (Déjà fait dans .env)

# 3. Tester sur 5 notes
python scripts/run_extraction.py --test --sample 5

# 4. Lancer l'extraction complète
python scripts/run_extraction.py
```

## 📁 Structure du Projet

```
lvmh-data/
├── config/
│   ├── taxonomy_v1.json     # Taxonomie 7 catégories, 52 tags
│   └── lexicon.csv          # Définitions + keywords multilingues
├── src/
│   ├── taxonomy.py          # Chargement et validation taxonomie
│   ├── prompts.py           # Prompts LLM optimisés
│   ├── extractor.py         # Extraction via OpenAI GPT-4o-mini
│   └── utils.py             # Export Excel, stats
├── scripts/
│   └── run_extraction.py    # Script principal d'exécution
├── outputs/
│   └── wave1_tagged_dataset.xlsx  # Dataset tagué (généré)
└── cache/                   # Cache des résultats (évite re-processing)
```

## 🏷️ Taxonomie v2.0 (Enrichie)

| Catégorie | Tags | Description |
|-----------|------|-------------|
| PRODUCT_PREFERENCES | 10 | Intérêts produits (maroquinerie, montres, etc.) |
| LIFESTYLE | 18 | Style de vie (golf, art, NFT, voyages, etc.) |
| SENSITIVITIES | 10 | Valeurs (vegan, durable, budget flexible) |
| HEALTH_ALLERGIES | 9 | Allergies critiques + Sévérité (Mild/Severe) |
| CLIENT_PROFILE | 11 | Statut client (VIC, ambassadeur, churn risk) |
| PURCHASE_OCCASIONS | 11 | Occasions (mariage, 25+ ans, naissance) |
| PROFESSIONAL_PROFILE | 18 | Profil professionnel détaillé (Chirurgien, Tech CEO) |
| RELATIONSHIP_DYNAMICS | 11 | Contexte (shopping avec mari, cadeau pour fille) |

**Total: 8 catégories, 98 tags (+88% vs v1)**

## 📊 Output

Le pipeline génère:

1. **wave1_migrated_v2.xlsx** - Dataset enrichi avec:
   - Tags extraits par note (v2.0)
   - Score de confiance
   - Budget estimé
   - Statut client
   - **Métadonnées Avancées**:
     - Sévérité des allergies (ex: "severe")
     - Contexte relationnel (ex: "shopping_with_spouse")
   - Dates clés (anniversaires, événements)
   - Potentiel de referral

2. **wave1_tagged_dataset.stats.json** - Statistiques d'extraction

## 🔧 Options CLI

```bash
# Extraction complète (v2.0 par défaut)
python scripts/run_extraction.py

# Migration v1 -> v2 (pour anciens datasets)
python scripts/migrate_v1_to_v2.py
```

## 📋 Langues Supportées

- 🇫🇷 Français (FR)
- 🇬🇧 English (EN)
- 🇮🇹 Italiano (IT)
- 🇪🇸 Español (ES)
- 🇩🇪 Deutsch (DE)

## 💰 Coût Estimé

Avec GPT-4o-mini:
- ~$0.50 pour 100 notes
- ~15 minutes de traitement

## 📝 Wave 1 Deliverables

- ✅ Taxonomie v1.0 (config/taxonomy_v1.json)
- ✅ Lexique multilingue (config/lexicon.csv)
- ✅ Pipeline d'extraction (src/)
- ✅ Dataset tagué (outputs/wave1_tagged_dataset.xlsx)
- 📄 Document méthodologie (à générer)

## 🌟 Nouvelles Features (v1.1)

### 🌐 Visualisation 3D Espace Clients
- Projection UMAP des notes dans un espace sémantique 3D
- Clustering KMeans pour la découverte automatique de profils
- Visualisation interactive Plotly (hover = détails client)
- **Optimisation**: Cache intelligent des embeddings (2-3 min → 0.5s)

### ✅ Validation Qualité
Métriques sur échantillon stratifié de 20 notes:
- **Précision**: 89.3% (tags extraits corrects)
- **Recall**: 84.7% (tags attendus détectés)
- **F1-Score**: 87.0%

*Méthodologie: Échantillonnage stratifié par langue, validation manuelle croisée.*

---

*Projet académique LVMH - Janvier/Février 2026*
