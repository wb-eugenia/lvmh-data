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

## 🏷️ Taxonomie v1.0

| Catégorie | Tags | Description |
|-----------|------|-------------|
| PRODUCT_PREFERENCES | 10 | Intérêts produits (maroquinerie, montres, etc.) |
| LIFESTYLE | 15 | Style de vie (golf, art, voyages, etc.) |
| SENSITIVITIES | 7 | Valeurs (vegan, durable, heritage) |
| HEALTH_ALLERGIES | 6 | Allergies critiques pour événements |
| CLIENT_PROFILE | 8 | Statut client (VIC, prospect, etc.) |
| PURCHASE_OCCASIONS | 7 | Occasions d'achat (cadeau, self-purchase) |
| PROFESSIONAL_PROFILE | 6 | Profil professionnel |

**Total: 7 catégories, 52 tags**

## 📊 Output

Le pipeline génère:

1. **wave1_tagged_dataset.xlsx** - Dataset enrichi avec:
   - Tags extraits par note
   - Score de confiance
   - Budget estimé
   - Statut client
   - Allergies/régimes alimentaires
   - Dates clés (anniversaires, événements)
   - Potentiel de referral

2. **wave1_tagged_dataset.stats.json** - Statistiques d'extraction

## 🔧 Options CLI

```bash
# Extraction complète
python scripts/run_extraction.py

# Mode test (affiche sans sauver)
python scripts/run_extraction.py --test --sample 5

# Sans cache (re-traiter tout)
python scripts/run_extraction.py --no-cache

# Effacer le cache
python scripts/run_extraction.py --clear-cache

# Fichier input/output personnalisé
python scripts/run_extraction.py -i data/input.csv -o outputs/custom.xlsx
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

---

*Projet académique LVMH - Janvier/Février 2026*
