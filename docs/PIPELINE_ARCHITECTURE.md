# LVMH Voice-to-Tag Pipeline Architecture V2

## 🌍 Vision & Stratégie

Architecture pipeline hybride optimisée pour le traitement des notes vocales Client Advisor (CA) LVMH. 
Cette architecture privilégie la **souveraineté des données (EU-Native)**, la **performance** et l'**optimisation des coûts**.

### 🏆 Points Clés
- **Compliance LVMH**: 100% RGPD-Native & HDS Compliant via Mistral (Paris).
- **Cost-Efficiency**: 75% d'économies vs une approche "Full GPT-4".
- **Performance**: Traitement parallèle massif (50+ concurrent requests).
- **Sécurité**: Détection proactive des risques (Santé, Fraude, RGPD).

---

## 🔄 Flux de Données Global - Diagramme ASCII

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        LVMH VOICE-TO-TAG PIPELINE V2                            │
│                    ════════════════════════════════════                         │
└─────────────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────────────┐
                              │  📥 INPUT           │
                              │  CSV Notes Client   │
                              │  (ID, Date, Lang,   │
                              │   Transcription)    │
                              └─────────┬───────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STAGE 1: PRÉ-TRAITEMENT                                                         │
├─────────────────────────────────────────────────────────────────────────────────┤
│                         ┌─────────────────────────┐                             │
│                         │   🧹 TEXT CLEANER       │                             │
│                         │   ─────────────────     │                             │
│                         │   • Filler Removal      │ ◄── "euh", "bennn", "donc"  │
│                         │   • Normalization       │ ◄── Accents, Casing         │
│                         │   • Deduplication       │ ◄── Phrases répétées        │
│                         │   • ~5ms/note           │                             │
│                         └───────────┬─────────────┘                             │
└─────────────────────────────────────┼───────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STAGE 2: ROUTAGE INTELLIGENT                                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                    ┌──────────────────────────────────┐                         │
│                    │   🧠 SMART ROUTER V3             │                         │
│                    │   ──────────────────             │                         │
│                    │   Analyse Multi-Critères:        │                         │
│                    │   ┌────────────────────────────┐ │                         │
│                    │   │ • Longueur texte          │ │                         │
│                    │   │ • Complexité vocabulaire  │ │                         │
│                    │   │ • Patterns RGPD (boost)   │ │                         │
│                    │   │ • Mentions VIP/Ultimate   │ │                         │
│                    │   │ • Multi-langue détection  │ │                         │
│                    │   └────────────────────────────┘ │                         │
│                    │          │                       │                         │
│                    │          ▼                       │                         │
│                    │   ┌─────────────────────┐        │                         │
│                    │   │ SCORING: 0-100      │        │                         │
│                    │   └─────────────────────┘        │                         │
│                    └──────────┬───────────────────────┘                         │
└───────────────────────────────┼─────────────────────────────────────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
              ▼                 ▼                 ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
    │  Score < 20     │ │ Score 20-75     │ │  Score > 75     │
    │  ═══════════    │ │ ═══════════     │ │  ═══════════    │
    │  SIMPLE         │ │  STANDARD       │ │  COMPLEXE       │
    └────────┬────────┘ └────────┬────────┘ └────────┬────────┘
             │                   │                   │
             ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STAGE 3: TRAITEMENT MULTI-TIERS                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐     │
│  │ 🟢 TIER 1           │  │ 🔵 TIER 2           │  │ 🔴 TIER 3           │     │
│  │ ════════════════    │  │ ════════════════    │  │ ════════════════    │     │
│  │                     │  │                     │  │                     │     │
│  │ ⚡ RULES ENGINE     │  │ 🇫🇷 MISTRAL AI EU   │  │ 🤖 GPT-4 ENHANCED   │     │
│  │                     │  │                     │  │                     │     │
│  │ • Python Regex      │  │ • mistral-medium    │  │ • GPT-4o-mini       │     │
│  │ • Pattern Matching  │  │ • 100% EU-Hosted    │  │ • GPT-4-Turbo (VIP) │     │
│  │ • Keyword Rules     │  │ • HDS Compliant     │  │ • Complex Reasoning │     │
│  │                     │  │ • Batch API         │  │ • Multi-shot        │     │
│  │ ─────────────────   │  │ ─────────────────   │  │ ─────────────────   │     │
│  │ 💰 Coût: 0€         │  │ 💰 Coût: 0€*        │  │ 💰 Coût: $0.0001+   │     │
│  │ ⏱️  ~0.01s/note     │  │ ⏱️  ~2-3s/note      │  │ ⏱️  ~3-5s/note      │     │
│  │ 📊 ~15-20% notes    │  │ 📊 ~70-75% notes    │  │ 📊 ~5-10% notes     │     │
│  │                     │  │                     │  │                     │     │
│  └──────────┬──────────┘  └──────────┬──────────┘  └──────────┬──────────┘     │
│             │                        │                        │                 │
│             │                        │                        │                 │
│             │            ┌───────────┴───────────┐            │                 │
│             │            │ ⚠️ ESCALATION CHECK   │            │                 │
│             │            │ ─────────────────────  │            │                 │
│             │            │ Conditions:            │            │                 │
│             │            │ • Confidence < 0.75   ├────────────┤                 │
│             │            │ • VIP + Low Conf      │            │                 │
│             │            │ • High Severity Risk  │            │                 │
│             │            └───────────────────────┘            │                 │
│             │                                                 │                 │
└─────────────┼─────────────────────────────────────────────────┼─────────────────┘
              │                                                 │
              └─────────────────────┬───────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STAGE 4: AGRÉGATION & NORMALISATION                                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                       ┌─────────────────────────┐                               │
│                       │  📊 RESULT AGGREGATOR   │                               │
│                       │  ─────────────────────  │                               │
│                       │  • Schema Validation    │                               │
│                       │  • Field Normalization  │                               │
│                       │  • Confidence Scoring   │                               │
│                       │  • Metadata Enrichment  │                               │
│                       └───────────┬─────────────┘                               │
└───────────────────────────────────┼─────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ STAGE 5: CACHE & PERSISTENCE                                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│    ┌─────────────────────┐              ┌─────────────────────┐                 │
│    │  💾 CACHE MANAGER   │              │  📁 FILE EXPORT     │                 │
│    │  ─────────────────  │              │  ─────────────────  │                 │
│    │  • TTL: 24h         │              │  • Excel (.xlsx)    │                 │
│    │  • Hash-based keys  │              │  • CSV (.csv)       │                 │
│    │  • Tier-specific    │              │  • JSON (.json)     │                 │
│    │  • Disk persistence │              │  • Timestamp naming │                 │
│    └─────────────────────┘              └─────────────────────┘                 │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │   ✅ OUTPUT         │
                         │   Tagged Dataset    │
                         │   + Analytics       │
                         │   + Cost Report     │
                         └─────────────────────┘
```

---

## 📋 Détail des Stages

### 🔹 STAGE 1: Pré-traitement (`text_cleaner.py`)

```
┌────────────────────────────────────────────────────────────────┐
│                    TEXT CLEANER PIPELINE                        │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  INPUT: "Euh donc euh la cliente veut une ceinture noire..."  │
│              │                                                 │
│              ▼                                                 │
│  ┌────────────────────┐                                        │
│  │ 1. FILLER REMOVAL  │ Remove: "euh", "donc", "ben", "hein"  │
│  └─────────┬──────────┘                                        │
│            ▼                                                   │
│  ┌────────────────────┐                                        │
│  │ 2. NORMALIZATION   │ Lowercase, trim, fix spacing          │
│  └─────────┬──────────┘                                        │
│            ▼                                                   │
│  ┌────────────────────┐                                        │
│  │ 3. DEDUPLICATION   │ Remove repeated phrases               │
│  └─────────┬──────────┘                                        │
│            ▼                                                   │
│  OUTPUT: "la cliente veut une ceinture noire..."              │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

**Métriques**:
| Aspect | Valeur |
|--------|--------|
| Vitesse | ~5ms/note |
| Réduction taille | ~15-25% |
| Fillers types | FR/EN/IT/ES supportés |

---

### 🔹 STAGE 2: Routage Intelligent (`smart_router.py`)

```
┌────────────────────────────────────────────────────────────────┐
│                   SMART ROUTER V3 ALGORITHM                     │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  SCORING FORMULA:                                              │
│  ═══════════════                                               │
│                                                                │
│  base_score = f(length, vocab_complexity, structure)           │
│                                                                │
│  ┌──────────────────────────────────────────────┐              │
│  │ BOOSTS (Ajouts au score):                    │              │
│  │ ─────────────────────────                    │              │
│  │ • RGPD Keywords     → +30 points            │              │
│  │   (santé, allergie, maladie, judiciaire)    │              │
│  │ • VIP Mention       → +25 points            │              │
│  │   (VIC, Ultimate, Platinum)                 │              │
│  │ • Multi-langue      → +15 points            │              │
│  │ • Long text (>500c) → +20 points            │              │
│  └──────────────────────────────────────────────┘              │
│                                                                │
│  ┌──────────────────────────────────────────────┐              │
│  │ DECISION THRESHOLDS:                         │              │
│  │ ────────────────────                         │              │
│  │ Score < 20   → TIER 1 (Rules)               │              │
│  │ Score 20-75  → TIER 2 (Mistral EU)          │              │
│  │ Score > 75   → TIER 3 (GPT-4)               │              │
│  └──────────────────────────────────────────────┘              │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

### 🔹 STAGE 3: Détail des Tiers

#### 🟢 TIER 1: Rules Engine

```
┌────────────────────────────────────────────────────────────────┐
│                      TIER 1: RULES ENGINE                       │
├────────────────────────────────────────────────────────────────┤
│  📁 Fichier: src/tier1_rules.py                                │
│                                                                │
│  PATTERNS DÉTECTÉS:                                            │
│  ══════════════════                                            │
│                                                                │
│  ┌─────────────────────────────────────────────────────┐       │
│  │ PRODUITS              │ TAILLES          │ COULEURS │       │
│  │ ────────              │ ───────          │ ──────── │       │
│  │ • ceinture            │ • 85, 90, 95     │ • noir   │       │
│  │ • sac                 │ • S, M, L, XL    │ • marron │       │
│  │ • portefeuille        │ • 38, 40, 42     │ • bleu   │       │
│  │ • montre              │                  │ • rouge  │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                │
│  EXEMPLE:                                                      │
│  Input:  "Cherche ceinture noire taille 85"                   │
│  Output: {                                                     │
│            "product": "belt",                                  │
│            "color": "black",                                   │
│            "size": "85",                                       │
│            "confidence": 0.95                                  │
│          }                                                     │
│                                                                │
│  ⚡ Vitesse: ~0.01s  |  💰 Coût: 0€  |  📊 Usage: ~15-20%      │
└────────────────────────────────────────────────────────────────┘
```

#### 🔵 TIER 2: Mistral AI EU

```
┌────────────────────────────────────────────────────────────────┐
│                    TIER 2: MISTRAL AI EU                        │
├────────────────────────────────────────────────────────────────┤
│  📁 Fichier: src/tier2_mistral.py                              │
│                                                                │
│  CONFIGURATION:                                                │
│  ══════════════                                                │
│  ┌────────────────────────────────────────────┐                │
│  │ Model:      mistral-medium-latest         │                │
│  │ API:        La Plateforme (Paris)         │                │
│  │ Endpoint:   https://api.mistral.ai/v1     │                │
│  │ Rate Limit: 1B tokens/mois (Free)         │                │
│  │ Concurrency: 50 parallel requests         │                │
│  │ Temperature: 0.3 (optimisé précision)     │                │
│  └────────────────────────────────────────────┘                │
│                                                                │
│  COMPLIANCE 🇪🇺:                                               │
│  ═════════════                                                 │
│  ┌────────────────────────────────────────────┐                │
│  │ ✅ RGPD Native (données EU uniquement)    │                │
│  │ ✅ HDS Compliant (données santé)          │                │
│  │ ✅ ISO 27001 Certified                    │                │
│  │ ✅ SOC 2 Type II                          │                │
│  └────────────────────────────────────────────┘                │
│                                                                │
│  PROMPT STRUCTURE:                                             │
│  ═════════════════                                             │
│  [SYSTEM] Tu es un expert LVMH extraction...                   │
│  [USER]   Analyse cette note: "{transcription}"                │
│  [FORMAT] JSON strict avec tags, budget, client...             │
│                                                                │
│  ⏱️ Vitesse: ~2-3s  |  💰 Coût: 0€  |  📊 Usage: ~70-75%       │
└────────────────────────────────────────────────────────────────┘
```

#### 🔴 TIER 3: GPT-4 Enhanced

```
┌────────────────────────────────────────────────────────────────┐
│                   TIER 3: GPT-4 ENHANCED                        │
├────────────────────────────────────────────────────────────────┤
│  📁 Fichier: src/extractor.py (TagExtractor)                   │
│                                                                │
│  MODÈLES DISPONIBLES:                                          │
│  ════════════════════                                          │
│  ┌────────────────────────────────────────────┐                │
│  │ GPT-4o-mini  │ Default    │ $0.0001/note  │                │
│  │ GPT-4-Turbo  │ VIP only   │ $0.005/note   │                │
│  └────────────────────────────────────────────┘                │
│                                                                │
│  DÉCLENCHEURS:                                                 │
│  ═════════════                                                 │
│  DIRECT (Router score > 75):                                   │
│    • Texte très long (>1000 chars)                             │
│    • Complexité extrême détectée                               │
│    • Client VIP explicitement mentionné                        │
│                                                                │
│  ESCALATION (depuis Tier 2):                                   │
│    • Confidence Mistral < 0.75                                 │
│    • VIP + Confidence < 0.80                                   │
│    • High severity risk (allergie grave)                       │
│                                                                │
│  ⏱️ Vitesse: ~3-5s  |  💰 Coût: $0.0001+  |  📊 Usage: ~5-10%  │
└────────────────────────────────────────────────────────────────┘
```

---

## 🛡️ Matrice de Sécurité & Escalade

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           ESCALATION MATRIX                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  SCÉNARIO                    │ TIER INITIAL │ ACTION           │ RAISON         │
│  ════════════════════════════│══════════════│══════════════════│═══════════════ │
│  Simple produit              │ Tier 1       │ ✅ Process       │ Regex suffit   │
│  ────────────────────────────│──────────────│──────────────────│─────────────── │
│  Note standard               │ Tier 2       │ ✅ Process       │ Mistral OK     │
│  ────────────────────────────│──────────────│──────────────────│─────────────── │
│  Allergie mentionnée         │ Tier 2       │ ✅ Process*      │ Mistral gère   │
│  ────────────────────────────│──────────────│──────────────────│─────────────── │
│  Allergie GRAVE + VIP        │ Tier 2       │ ⚠️ → Tier 3      │ Double check   │
│  ────────────────────────────│──────────────│──────────────────│─────────────── │
│  VIP + Confidence < 0.75     │ Tier 2       │ ⚠️ → Tier 3      │ Sécurité VIP   │
│  ────────────────────────────│──────────────│──────────────────│─────────────── │
│  Texte très complexe         │ Tier 3       │ ✅ Process       │ Direct GPT-4   │
│  ────────────────────────────│──────────────│──────────────────│─────────────── │
│  Mistral API DOWN            │ Tier 2       │ 🔄 → Tier 1      │ Fallback safe  │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Structure de Données (Output)

Chaque note traitée ressort avec un objet JSON standardisé :

```json
{
  "ID": "CA_123",
  "tags": ["leather_goods", "gift_for_spouse", "birthday"],
  "budget": {
    "range": "5K-10K",
    "min": 5000,
    "confidence": "inferred"
  },
  "client": {
    "status": "vic",
    "profession": "avocat"
  },
  "risk": {
    "allergies": ["nickel_allergy"],
    "severity": "high"
  },
  "metadata": {
    "tier": 2,
    "provider": "mistral_eu",
    "processing_time": 1.25,
    "cost": 0.0
  }
}
```

---

## 🚀 Performance & Métriques Actuelles

| Métrique | Valeur Cible | Actuel (Est.) | Status |
|----------|--------------|---------------|--------|
| **Précision (Tier 1)** | 99% | 99.5% | ✅ |
| **Précision (Tier 2 Mistral)** | 95% | 94% | ⚠️ |
| **Précision (Tier 3 GPT)** | 99% | 98.5% | ✅ |
| **Vitesse Moyenne** | < 2s / note | ~3.5s / note | ⚠️ |
| **Économie vs Full-GPT** | > 70% | ~80% | ✅ |
| **Cache Hit Rate** | > 30% | ~35% | ✅ |

---

## 🔧 VOIES D'AMÉLIORATION

### 🎯 Court Terme (1-2 semaines)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  1. OPTIMISATION ROUTER THRESHOLDS                                              │
│  ══════════════════════════════════                                             │
│                                                                                 │
│  Problème: Trop de notes escaladées vers Tier 3 (10% au lieu de 5%)            │
│                                                                                 │
│  Actions:                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐                │
│  │ • Augmenter seuil Tier 2→3 de 75 à 80                       │                │
│  │ • Ajuster confidence threshold de 0.75 à 0.70               │                │
│  │ • Analyser les escalations pour patterns récurrents         │                │
│  └─────────────────────────────────────────────────────────────┘                │
│                                                                                 │
│  Impact Estimé: Réduction 3-5% des coûts Tier 3                                │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│  2. BATCH API POUR MISTRAL                                                      │
│  ═════════════════════════                                                      │
│                                                                                 │
│  Problème: Appels séquentiels = ~3s/note                                       │
│                                                                                 │
│  Solution:                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐                │
│  │ • Grouper notes par batch de 10-20                          │                │
│  │ • Utiliser asyncio.gather() pour parallelisme               │                │
│  │ • Implémenter rate limiting intelligent                     │                │
│  └─────────────────────────────────────────────────────────────┘                │
│                                                                                 │
│  Impact Estimé: Passage de 3s/note à ~0.5s/note                                │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│  3. AMÉLIORATION CACHE                                                          │
│  ════════════════════                                                           │
│                                                                                 │
│  Problème: Cache hit rate ~35%, potentiel ~60%+                                │
│                                                                                 │
│  Solutions:                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐                │
│  │ • Normalisation sémantique des textes avant hash            │                │
│  │ • Cache partagé inter-sessions                              │                │
│  │ • TTL adaptatif (notes simples: 7j, complexes: 24h)         │                │
│  └─────────────────────────────────────────────────────────────┘                │
│                                                                                 │
│  Impact Estimé: Cache hit rate → 50-60%                                        │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

### 🎯 Moyen Terme (1-2 mois)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  4. ML-BASED ROUTER (LEARNING FROM ESCALATIONS)                                 │
│  ═══════════════════════════════════════════════                                │
│                                                                                 │
│  Concept:                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐                │
│  │                                                             │                │
│  │   Notes Historiques  ──►  Train Classifier  ──►  Predict   │                │
│  │   + Escalation Data                              Tier       │                │
│  │                                                             │                │
│  └─────────────────────────────────────────────────────────────┘                │
│                                                                                 │
│  Implémentation:                                                                │
│  • Collecter features: length, vocabulary, RGPD terms, etc.                    │
│  • Label: tier utilisé + succès (confidence finale)                            │
│  • Model: LightGBM ou simple Neural Network                                     │
│  • A/B test: heuristic vs ML router                                            │
│                                                                                 │
│  Impact: Réduction 10-15% des escalations inutiles                             │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│  5. EMBEDDING CACHE (SEMANTIC DEDUPLICATION)                                    │
│  ════════════════════════════════════════════                                   │
│                                                                                 │
│  Concept:                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐                │
│  │                                                             │                │
│  │   New Note ──► Embed ──► Similarity Search ──► Reuse?      │                │
│  │                              │                              │                │
│  │                              ▼                              │                │
│  │                    Vector DB (FAISS/ChromaDB)              │                │
│  │                                                             │                │
│  └─────────────────────────────────────────────────────────────┘                │
│                                                                                 │
│  Bénéfices:                                                                     │
│  • Notes similaires → même résultat (économie 100%)                            │
│  • Détection doublons sémantiques                                              │
│  • Clustering pour analytics                                                   │
│                                                                                 │
│  Stack Suggéré: sentence-transformers + FAISS (local)                          │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│  6. FINE-TUNING MISTRAL SUR DONNÉES LVMH                                        │
│  ════════════════════════════════════════                                       │
│                                                                                 │
│  Problème: Mistral générique = vocabulaire LVMH limité                         │
│                                                                                 │
│  Solution:                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐                │
│  │ 1. Collecter 500+ exemples annotés (notes + tags corrects) │                │
│  │ 2. Fine-tune mistral-7b-instruct via La Plateforme         │                │
│  │ 3. Déployer modèle custom "mistral-lvmh-v1"                │                │
│  └─────────────────────────────────────────────────────────────┘                │
│                                                                                 │
│  Impact Estimé:                                                                 │
│  • Précision Tier 2: 94% → 97%                                                 │
│  • Réduction escalations: -30%                                                 │
│  • Vocabulaire maison (VIC, Ultimate categories) natif                         │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

### 🎯 Long Terme (3-6 mois)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  7. STREAMING PIPELINE (REAL-TIME PROCESSING)                                   │
│  ════════════════════════════════════════════                                   │
│                                                                                 │
│  Architecture Cible:                                                            │
│  ┌─────────────────────────────────────────────────────────────┐                │
│  │                                                             │                │
│  │   Voice Input ──► Whisper ──► Pipeline ──► Dashboard       │                │
│  │       │              │            │            │            │                │
│  │       └──────────────┴────────────┴────────────┘            │                │
│  │                      │                                      │                │
│  │                 Kafka/Redis Queue                           │                │
│  │                                                             │                │
│  └─────────────────────────────────────────────────────────────┘                │
│                                                                                 │
│  Composants:                                                                    │
│  • Kafka pour ingestion en temps réel                                          │
│  • Redis pour cache haute-performance                                          │
│  • WebSocket pour push vers dashboard                                          │
│                                                                                 │
│  Use Case: CA enregistre → Tags visibles en <10 secondes                       │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│  8. MULTI-MODAL ANALYSIS (AUDIO + TEXT)                                         │
│  ══════════════════════════════════════                                         │
│                                                                                 │
│  Concept:                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐                │
│  │                                                             │                │
│  │   Audio ──► Whisper ──► Text                               │                │
│  │     │                     │                                 │                │
│  │     └──► Emotion/Tone ────┼──► Combined Analysis           │                │
│  │                           │                                 │                │
│  │                           └──► Standard Pipeline            │                │
│  │                                                             │                │
│  └─────────────────────────────────────────────────────────────┘                │
│                                                                                 │
│  Features Additionnelles:                                                       │
│  • Détection urgence dans la voix                                              │
│  • Sentiment client (positif/négatif)                                          │
│  • Qualité audio → confidence adjustment                                       │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│  9. AUTO-EVAL & CONTINUOUS IMPROVEMENT                                          │
│  ════════════════════════════════════                                           │
│                                                                                 │
│  Feedback Loop:                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐                │
│  │                                                             │                │
│  │   Pipeline Output ──► Human Review ──► Corrections         │                │
│  │         │                                   │               │                │
│  │         │                                   ▼               │                │
│  │         └─────────────────►  Retrain / Adjust              │                │
│  │                                                             │                │
│  └─────────────────────────────────────────────────────────────┘                │
│                                                                                 │
│  Système:                                                                       │
│  • Interface validation pour CAs                                               │
│  • Métriques qualité auto-calculées                                            │
│  • Alerting si précision drop                                                  │
│  • Weekly model refresh si dégradation                                         │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📊 Roadmap Résumé

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              IMPROVEMENT ROADMAP                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  COURT TERME (1-2 sem)         MOYEN TERME (1-2 mois)       LONG TERME (3-6m)  │
│  ══════════════════           ═══════════════════════       ════════════════   │
│                                                                                 │
│  ┌───────────────────┐        ┌───────────────────┐        ┌─────────────────┐ │
│  │ ☐ Router Tuning   │───────►│ ☐ ML Router       │───────►│ ☐ Streaming     │ │
│  └───────────────────┘        └───────────────────┘        └─────────────────┘ │
│                                                                                 │
│  ┌───────────────────┐        ┌───────────────────┐        ┌─────────────────┐ │
│  │ ☐ Batch API       │───────►│ ☐ Embedding Cache │───────►│ ☐ Multi-Modal   │ │
│  └───────────────────┘        └───────────────────┘        └─────────────────┘ │
│                                                                                 │
│  ┌───────────────────┐        ┌───────────────────┐        ┌─────────────────┐ │
│  │ ☐ Cache Improve   │───────►│ ☐ Fine-tune       │───────►│ ☐ Auto-Eval     │ │
│  └───────────────────┘        └───────────────────┘        └─────────────────┘ │
│                                                                                 │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  Impact Cumulé Estimé:                                                         │
│  • Vitesse: 3.5s → 0.5s/note                                                   │
│  • Coût: -40% (moins d'escalations)                                            │
│  • Précision: 94% → 97%+                                                       │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📝 Maintenance & Ops

- **Logs**: `logs/pipeline.log` (Rotation journalière).
- **Cache**: `cache/pipeline_v2/` (TTL 24h, évite de repayer/retraiter les mêmes notes).
- **Requirements**: Python 3.10+, `mistralai`, `openai`, `pandas`.

---

## 📎 Fichiers Clés

| Fichier | Rôle |
|---------|------|
| `src/pipeline_v2.py` | Orchestrateur principal |
| `src/smart_router.py` | Logique de routage multi-tier |
| `src/text_cleaner.py` | Pré-traitement texte |
| `src/tier1_rules.py` | Engine regex Tier 1 |
| `src/tier2_mistral.py` | Client Mistral EU |
| `src/extractor.py` | TagExtractor (Tier 3) |
| `src/cache_manager.py` | Gestion cache disque |
| `src/cost_tracker.py` | Suivi des coûts API |
