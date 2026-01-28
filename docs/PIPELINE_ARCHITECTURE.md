# LVMH Voice-to-Tag Pipeline Architecture

## 🔄 Vue d'Ensemble

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LVMH VOICE-TO-TAG PIPELINE V2                       │
│                         Multi-Tier Extraction Engine                        │
└─────────────────────────────────────────────────────────────────────────────┘

                              ┌──────────────┐
                              │  📝 INPUT    │
                              │  CSV Notes   │
                              │  (300 notes) │
                              └──────┬───────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          🧹 TEXT CLEANER                                    │
│                      (src/text_cleaner.py)                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  • Protection entités business (dates, montants, codes)             │    │
│  │  • Suppression fillers ("euhhh", "beeeen", "hmmmm")                 │    │
│  │  • Normalisation variants orthographiques                           │    │
│  │  • Déduplication sémantique (phrases répétées)                      │    │
│  │  Cost: 0€ | Speed: ~5ms/note                                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          🧠 SMART ROUTER V3                                 │
│                  (Heuristic Scoring + ML Learning + RGPD Boost)             │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  SCORING (0-100 points):                                            │    │
│  │  ├── Text Complexity     (25 pts) : longueur, structure             │    │
│  │  ├── Linguistic Quality  (20 pts) : franglais, fautes               │    │
│  │  ├── Business Criticality(30 pts) : VIC, budget, allergies          │    │
│  │  ├── Intent Type         (15 pts) : conseil, comparaison, négation  │    │
│  │  └── Risk Flags          (10 pts) : RGPD, fraude                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  🔒 RGPD BOOST (Intégré - 0.1ms):                                   │    │
│  │  • Détection: diabète, cancer, dépression, divorce, procès...      │    │
│  │  • Si détecté → +30 pts → Force Tier 2 minimum (skip Tier 1)        │    │
│  │  • 1000x plus rapide que l'ancien Ollama filter!                    │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  ML ENHANCEMENT:                                                    │    │
│  │  • record_feedback() → Apprend des escalations                      │    │
│  │  • train_model()     → RandomForest (class_weight='balanced')       │    │
│  │  • route_ml()        → Hybrid: ML si confiant, sinon heuristic      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
                    ▼                ▼                ▼
        ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
        │   TIER 1      │  │   TIER 2      │  │   TIER 3      │
        │   RULES       │  │   GROQ        │  │   GPT-4       │
        └───────────────┘  └───────────────┘  └───────────────┘
        │   Score < 20  │  │  Score 20-75  │  │  Score > 75   │
        │  (NO RGPD!)   │  │  (RGPD here)  │  │  ou Override  │
        │   💰 FREE     │  │   💰 ~FREE    │  │   💰 $0.005   │
        │   ⏱️ 50ms     │  │   ⏱️ 3s       │  │   ⏱️ 5s       │
        └───────┬───────┘  └───────┬───────┘  └───────┬───────┘
                │                  │                  │
                ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TIER 1: RULES ENGINE                           │
│                           (src/tier1_rules.py)                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  • Regex patterns pour tags simples                                 │    │
│  │  • Budget extraction (e.g., "5K" → budget_min: 5000)                │    │
│  │  • Catégories basiques (sac, montre, ceinture)                      │    │
│  │  • Pas de LLM → Ultra-rapide                                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                              TIER 2: GROQ ENGINE                            │
│                           (src/tier2_groq.py)                               │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Model: llama-3.3-70b-versatile                                     │    │
│  │  • Extraction Layer 1 (Taxonomy 98 tags)                            │    │
│  │  • Extraction Layer 2 (Entités: marques, lieux, événements)         │    │
│  │  • Allergies, régimes, occasions                                    │    │
│  │  • Async + Timeout 15s + Circuit Breaker                            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  ESCALATION CONDITIONS → Tier 3:                                    │    │
│  │  • allergy_severity == 'high'                                       │    │
│  │  • client_status in ['vic', 'ultimate'] + confidence < 0.9          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           TIER 3: GPT-4 ENHANCED                            │
│                           (src/extractor.py)                                │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  4-LAYER EXTRACTION:                                                │    │
│  │  ├── Layer 1: Taxonomy (98 tags LVMH)                               │    │
│  │  ├── Layer 2: Entities (marques, lieux, événements, produits)       │    │
│  │  ├── Layer 3: Implicit Signals (urgence, sentiment, objections)     │    │
│  │  └── Layer 4: Risks (allergies, RGPD, fraude)                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  ADAPTIVE MODEL SELECTION:                                          │    │
│  │  • gpt-4o-mini   : Economy fallback                                 │    │
│  │  • gpt-4o        : Standard (default)                               │    │
│  │  • gpt-4-turbo   : Premium (VIC Ultimate, texte long)               │    │
│  │  • o1-mini       : Reasoning (cas ambigus)                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  FEATURES:                                                          │    │
│  │  • Full Async (AsyncOpenAI, semaphore)                              │    │
│  │  • Smart Cache (TTL 24h, JSON local)                                │    │
│  │  • Robust Validation (Pydantic + fallback parsing)                  │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            📊 OUTPUT                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  ExtractionResult:                                                  │    │
│  │  ├── tags: List[str]           (98 taxonomy tags)                   │    │
│  │  ├── budget_min/max: int       (inferred from context)              │    │
│  │  ├── client_status: str        (vip, vic, ultimate, regular)        │    │
│  │  ├── allergies: List[str]      (with severity)                      │    │
│  │  ├── entities: Dict            (brands, locations, events)          │    │
│  │  ├── implicit_signals: Dict    (urgency, sentiment, objections)     │    │
│  │  ├── risk_flags: Dict          (allergy_emergency, rgpd, fraud)     │    │
│  │  ├── confidence: float         (0-1)                                │    │
│  │  └── processing_tier: int      (1, 2, or 3)                         │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  📁 Exports: Excel, CSV, JSON                                               │
└─────────────────────────────────────────────────────────────────────────────┘


## 📈 Métriques Attendues

┌─────────────────────────────────────────────────────────────────────────────┐
│                          DISTRIBUTION OPTIMALE                              │
├─────────────────┬───────────┬────────────┬─────────────────────────────────┤
│      Tier       │    %      │   Coût     │         Usage                   │
├─────────────────┼───────────┼────────────┼─────────────────────────────────┤
│  Tier 1 (Rules) │   ~20%    │    FREE    │  Cas simples, lookups           │
│  Tier 2 (Groq)  │   ~55%    │   ~FREE    │  Majorité, balance coût/qualité │
│  Tier 3 (GPT-4) │   ~25%    │  $0.005/n  │  VIC, allergies, ambigus        │
├─────────────────┼───────────┼────────────┼─────────────────────────────────┤
│  TOTAL 300      │   100%    │  ~$0.375   │  vs $1.50 (all GPT-4)           │
│                 │           │            │  ÉCONOMIE: 75%                  │
└─────────────────┴───────────┴────────────┴─────────────────────────────────┘


## 🔄 Flux de Feedback ML

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Route      │────▶│   Execute    │────▶│   Evaluate   │
│  (predict)   │     │  (Tier X)    │     │  (confidence)│
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                 │
                     ┌───────────────────────────┴───────────────────────────┐
                     │                                                       │
                     ▼                                                       ▼
            ┌──────────────┐                                        ┌──────────────┐
            │  Confidence  │                                        │  Confidence  │
            │    >= 0.8    │                                        │    < 0.8     │
            │   SUCCESS    │                                        │   ESCALATE   │
            └──────┬───────┘                                        └──────┬───────┘
                   │                                                       │
                   ▼                                                       ▼
            ┌──────────────┐                                        ┌──────────────┐
            │  Feedback:   │                                        │  Feedback:   │
            │  final_tier  │                                        │  final_tier  │
            │  = executed  │                                        │  = higher    │
            └──────┬───────┘                                        └──────┬───────┘
                   │                                                       │
                   └───────────────────────┬───────────────────────────────┘
                                           │
                                           ▼
                                    ┌──────────────┐
                                    │   ML Model   │
                                    │  (retrain    │
                                    │   weekly)    │
                                    └──────────────┘
```
