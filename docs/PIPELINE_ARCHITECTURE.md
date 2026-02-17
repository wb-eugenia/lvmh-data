# LVMH Data Pipeline Architecture V2 (Batch Optimized)

## 🌍 Vision & Stratégie

Architecture pipeline hybride **Batch-First** optimisée pour le traitement des notes vocales Client Advisor (CA) LVMH.
Cette architecture privilégie la **souveraineté des données (EU-Native)**, la **performance extrême (Async/Parallel)** et l'**optimisation des coûts**.

### 🏆 Performance & Benchmarks (Jan 2026)
- **Vitesse**: ~26ms/note (300 notes en 7.9s).
- **Architecture**: Pratique du "Route-First, Group-by-Tier, Process-Parallel".
- **Scalabilité**: Capable de traiter 10,000 notes en <5 minutes.
- **Cost-Efficiency**: 80% d'économies vs "Full GPT-4".

---

## 🔄 Flux de Données Global - Diagramme ASCII

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    LVMH BATCH PIPELINE V2 ARCHITECTURE                          │
│                    ════════════════════════════════════                         │
│                  "Route All → Group → Parallel Process"                         │
└─────────────────────────────────────────────────────────────────────────────────┘

                               ┌─────────────────────┐
                               │  📥 INPUT           │
                               │  CSV Notes Client   │
                               │  (Batch: 50-500+)   │
                               └─────────┬───────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: ROUTING MASSIF (Single Pass)                                           │
├─────────────────────────────────────────────────────────────────────────────────┤
│                    ┌──────────────────────────────────┐                         │
│                    │   🧠 SMART ROUTER V3             │                         │
│                    │   ──────────────────             │                         │
│                    │   • Fast-Path (5ms/note)        │                         │
│                    │   • RGPD & Complexity Scoring    │                         │
│                    │   • Routing Decision (Tagging)   │                         │
│                    └──────────┬───────────────────────┘                         │
│                               │                                                 │
│                        Decisions (T1, T2, T3)                                   │
│                               │                                                 │
└───────────────────────────────┼─────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: GROUPING & OPTIMIZATION                                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│          [Group T1]        [Group T2]        [Group T3]                         │
│          90 notes          199 notes         11 notes                           │
│             │                 │                 │                               │
│             ▼                 ▼                 ▼                               │
│                                                                                 │
└───────────────────────────────┼─────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ PHASE 3: PARALLEL ASYNC PROCESSING                                              │
├─────────────────────────────────────────────────────────────────────────────────┤
│  Asyncio.gather(                                                                │
│                                                                                 │
│    ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐              │
│    │ 🟢 TIER 1       │   │ 🔵 TIER 2       │   │ 🔴 TIER 3       │              │
│    │ RULES ENGINE    │   │ MISTRAL ASYNC   │   │ GPT-4 ENHANCED  │              │
│    │ ════════════    │   │ ════════════    │   │ ════════════    │              │
│    │                 │   │                 │   │                 │              │
│    │ • Context Regex │   │ • Batch API     │   │ • 4-Layer Deep  │              │
│    │ • Smart Budget  │   │ • 50 concurrent │   │ • Logic Chains  │              │
│    │ • Relations     │   │ • 0.5s/note     │   │ • Fallback Safes│              │
│    │                 │   │                 │   │                 │              │
│    └───────┬─────────┘   └────────┬────────┘   └────────┬────────┘              │
│            │                      │                     │                       │
│  )         ▼                      ▼                     ▼                       │
│                                                                                 │
└───────────────────────────────┼─────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│ PHASE 4: MERGE & VALIDATION                                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                       ┌─────────────────────────┐                               │
│                       │  🔄 RESULT MERGER       │                               │
│                       │  ─────────────────────  │                               │
│                       │  • Preserve Order       │                               │
│                       │  • Escalation Handling  │                               │
│                       │  • Cache Validation     │                               │
│                       └───────────┬─────────────┘                               │
│                                   │                                             │
└───────────────────────────────────┼─────────────────────────────────────────────┘
                                    ▼
                         ┌─────────────────────┐
                         │   ✅ OUTPUT         │
                         │   Tagged Dataset    │
                         └─────────────────────┘
```

---

## 📋 Détail des Composants Techniques

### 🔹 Stage 1: Smart Routing & Grouping
Le routeur analyse chaque note en ~5ms pour déterminer la complexité. 
*Nouvel ajout*: Groupement par Tier avant traitement pour optimiser les appels API (éviter de mélanger des appels rapides et lents).

### 🔹 Stage 2: Tiers de Traitement (Mise à jour V2)

#### 🟢 TIER 1: Rules Engine Enhanced (`tier1_rules.py`)
Moteur heuristique déterministe amélioré avec inférence contextuelle.
*   **Smart Budget**: Déduit des ranges (ex: "High Budget" si VIC mentionné) même sans montant explicite.
*   **Relations**: Identifie les contextes d'achat ("Cadeau pour épouse", "Pour sa fille").
*   **Performance**: Pré-compilation des regex pour vitesse maximale.

#### 🔵 TIER 2: Mistral Async (`tier2_mistral.py`)
Traitement de masse via Mistral Medium (EU-Hosted).
*   **Async Batching**: Utilisation de sémaphores (50 concurrents) pour traiter les notes en parallèle.
*   **Retry Logic**: Robustesse face aux erreurs API.
*   **Escalation**: Détection intelligente des cas ambigus nécessitant le Tier 3.

#### 🔴 TIER 3: GPT-4 Enhanced (`extractor.py`)
L'analyseur le plus puissant pour les cas critiques (VIP Ultimate, Allergies Sévères, Ambiguïté).
Il opère désormais une **Analyse en 4 Couches (Deep 4-Layer Extraction)** :
1.  **Layer 1 - Taxonomie**: Tags standards (Produits, Couleurs).
2.  **Layer 2 - Entités Dynamiques**: Marques, Lieux, Événements spécifiques.
3.  **Layer 3 - Intentions Implicites**: Signaux émotionnels, opportunités non-dites.
4.  **Layer 4 - Risques & Alertes**: Allergies (Gravité classifiée), RGPD.

**Architecture Technique**:
*   Entièrement **Asynchrone** (Async/Await) - *Corrige les problèmes de blocage*.
*   Support des modèles **Adaptive** (GPT-4o, o1-reasoning).

---

## 🛡️ Matrice de Sécurité & Escalade (Mise à jour)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           ESCALATION PROTOCOLS                                   │
│  "Safety First, Efficiency Second"                                              │
└─────────────────────────────────────────────────────────────────────────────────┘

1. DETECTION INITIALE (PRE-FLIGHT)
   • Note contient "choc anaphylactique" → FORCE TIER 3
   • Client "Ultimate" identifié         → FORCE TIER 3

2. DYNAMIC ESCALATION (DURING FLIGHT)
   • Tier 2 détecte "Allergie High Severity" → Escalade vers Tier 3
   • Tier 2 Confidence Score < 0.85          → Escalade vers Tier 3
   
3. FALLBACKS
   • Tier 3 Fail → Tier 2 Retry
   • Tier 2 Fail → Tier 1 (Safe Mode)
```

---

## 🚀 Performance Comparée (V1 vs V2)

| Métrique | Pipe Séquentiel (V1) | Pipe Batch (V2) | Gain |
|----------|----------------------|-----------------|------|
| **Vitesse (300 notes)** | 14m 30s | **7.9s** | **~110x** |
| **Vitesse / note** | 2900ms | **26ms** | 🚀 |
| **Concurrency** | 1 | **50+** | ✅ |
| **API Errors** | Fréquent (Timeout) | **Géré (Backoff)** | ✅ |

---

## 🔧 ROADMAP & FUTUR (Mise à jour)

### ✅ FAIT (Delivered)
*   [x] **Batch Pipeline Architecture** (`pipeline_batch.py`)
*   [x] **Async Mistral Integration**
*   [x] **Tier 1 Context Awareness**
*   [x] **Fix Tier 3 Async Issues**
*   [x] **Cache Optimization** (`from_cache` field)

### 🎯 PLANIFIÉ (Next Steps)
1.  **ML-Based Router (V4)**: Remplacer les règles heuristiques du routeur par un modèle léger (LightGBM) entraîné sur les résultats historiques pour prédire le Tier optimal avec 98% de précision.
2.  **Streaming Pipeline**: Architecture Kafka pour l'ingestion temps réel.
3.  **Multi-Modal**: Intégration de l'analyse audio (tonalité) avec Whisper.

---

## 📎 Fichiers Clés (Architecture V2)

| Fichier | Rôle |
|---------|------|
| `src/pipeline_batch.py` | **Core Orchestrator** (Batch, Async, Parallel) |
| `src/smart_router.py` | Logique de routage & Scoring |
| `src/tier1_rules.py` | Engine Regex Amélioré |
| `src/tier2_mistral.py` | Client Mistral Async |
| `src/extractor.py` | Tier 3 Enhanced (GPT-4 Deep Layer) |
| `src/models.py` | Schémas de données Pydantic Strict |
| `config/production.py` | Settings & API Keys |
