# LVMH Voice-to-Tag Pipeline - Runtime Complet (Référence Production)

**Date de référence:** 11 février 2026  
**Version runtime observée:** branche `walid`  
**Objectif de ce document:** décrire exactement ce qui tourne, pourquoi les choix ont été faits, et ce qui reste à finaliser pour une prod stricte.

---

## 1) Résumé exécutif

La pipeline transforme une note vocale/texte de Client Advisor en sortie CRM structurée autour des 4 piliers LVMH:
- Pilier 1: Univers Produit
- Pilier 2: Profil Client
- Pilier 3: Hospitalité & Care
- Pilier 4: Action Business (NBA)

Le design est volontairement **tiered** pour équilibrer:
- **Qualité** (notes complexes traitées par modèle premium),
- **Coût** (les cas simples restent en règles/tiers moins chers),
- **Latence** (concurrence asynchrone),
- **Conformité RGPD** (anonymisation + filtre contextuel + fallback local).

---

## 2) Providers réels en runtime (précis)

### 2.1 Chemin actif
- **Transcription audio**: OpenAI Whisper (`whisper-1`) via `POST /api/transcribe`.
- **Tier 1 extraction**: Regex rules (`Tier1RulesEngine`).
- **Tier 2 extraction**: Mistral (`Tier2Mistral`).
- **Tier 3 extraction**: Mistral premium (`TagExtractor` / `Tier3Enhanced`).
- **RAG**: SentenceTransformers + FAISS (`ProductMatcher`).
- **RGPD contextuel**: OpenAI (`RGPDFilter`) + fallback heuristique local.
- **Routing ML**: RandomForest `scikit-learn` + heuristique Smart Router.

### 2.2 Non actif (rangé legacy)
- Modules Groq déplacés dans `archive/legacy_groq/`:
  - `archive/legacy_groq/tier2_groq_legacy.py`
  - `archive/legacy_groq/tier2_whisper_legacy.py`
  - `archive/legacy_groq/event_pipeline_legacy.py`
- Shims de compatibilité dans `src/`:
  - `src/tier2_groq.py` (deprecated, fail-fast)
  - `src/tier2_whisper.py` (deprecated, fail-fast)
  - `src/event_pipeline.py` (shim vers `api.main:app`)

---

## 3) Flux technique complet (step-by-step)

## 3.1 API Gateway (FastAPI)
- Entrée unique via `api/main.py`.
- Routes actives: analyze, batch, results, stats, transcribe, auth, streaming, feedback, dashboard.
- Pourquoi ce choix:
  - async natif,
  - docs OpenAPI immédiates,
  - intégration frontend simple.

## 3.2 Auth/RBAC
- Login OAuth2 password (`/api/auth/login`) + JWT.
- Rôles: advisor/manager.
- `POST /api/analyze` et `GET /api/history` sont en auth stricte.
- Pourquoi:
  - séparation des droits,
  - auditabilité,
  - durcissement prod.

## 3.3 Cleaning (pré-traitement)
- Normalisation texte, suppression fillers, anti-dup, masquage PII.
- Pourquoi:
  - réduire bruit et tokens,
  - stabiliser extraction,
  - limiter fuite de données sensibles.

## 3.4 Couche RGPD
- Étape RGPD explicite dans `AsyncPipeline`.
- Mode principal: `RGPDFilter` (LLM contextuel).
- Fallback: heuristique local (markers PII) si LLM indispo/erreur.
- Pourquoi:
  - conformité robuste même en incident provider.

## 3.5 Smart Router V3 (Heuristique + ML)
- Score de complexité 0-100.
- Décision hybride:
  - heuristique de sécurité,
  - proposition ML RandomForest,
  - safety floor pour éviter downgrade dangereux.
- Pourquoi:
  - coût maîtrisé,
  - maintien de qualité sur cas sensibles.

## 3.6 Extraction Tiered
- Tier 1: ultra rapide, déterministe.
- Tier 2: Mistral medium/balanced pour volume standard.
- Tier 3: Mistral large pour ambigu/critique.
- Cross-validation des tiers si multi-sorties.
- Pourquoi:
  - latence acceptable,
  - précision plus élevée sur cas difficiles.

## 3.7 RAG Produit
- Matching sémantique sur index produits vectorisé.
- Injection de `matched_products` dans Pilier 1.
- Pourquoi:
  - réduire hallucinations,
  - connecter note libre au catalogue réel.

## 3.8 Recommandation NBA
- `RecommenderEngine` enrichit le Pilier 4.
- Sortie actionnable: action_type, priorité, description, etc.
- Pourquoi:
  - transformer l’extraction en actions commerciales concrètes.

## 3.9 Gamification & persistence
- Score qualité, points advisor, historique.
- Stockage SQL (notes, feedback).
- Pourquoi:
  - adoption terrain,
  - boucle d’amélioration continue.

## 3.10 Feedback learning (ML Router)
- Enregistrement feedback online.
- Ré-entraînement possible via endpoint feedback/train.
- Pourquoi:
  - adaptation aux données réelles magasin.

## 3.11 Frontend Advisor/Manager
- Advisor: record/transcribe/analyze + feedback direct.
- Manager: KPI pipeline, qualité, coûts, composants, enregistrements.
- Pourquoi:
  - pilotage opérationnel temps réel.

---

## 4) Pourquoi ces choix (trade-offs)

## 4.1 Mistral pour extraction Tier 2/3
- Alignement souveraineté EU.
- Qualité stable sur extraction structurée FR/EN.
- Meilleur compromis coût/latence pour le cœur de pipeline.

## 4.2 OpenAI pour Whisper + RGPD contextuel
- Whisper-1: API robuste pour transcription audio.
- RGPDFilter LLM: meilleure détection contextuelle qu’un simple regex.
- Fallback local conservé pour continuité de service.

## 4.3 RandomForest pour routing
- Rapide à entraîner/inférer.
- Plus interprétable qu’un modèle opaque lourd.
- Suffisant pour tri 3 classes (tiers 1/2/3).

## 4.4 FAISS + embeddings pour RAG
- Recherche vectorielle locale performante.
- Scalabilité correcte catalogue produit.
- Réduction hallucinations via preuve catalogue.

## 4.5 FastAPI async + React Vite
- Productivité élevée,
- DX simple,
- facilité de déploiement conteneurisé.

---

## 5) Benchmarks qualité récents (100 notes, run live)

## 5.1 Pipeline directe
Fichier: `benchmark_quality_100_pipeline_live.json`
- Notes demandées: 100
- Notes traitées: 100
- Succès: 100%
- Durée: 296.18s
- Throughput: 20.26 notes/min
- Qualité moyenne: 60.5
- Confiance moyenne: 0.9137
- Tags moyens: 11.39
- Notes sans tags: 0%
- RAG hit rate: 90%
- RGPD sensible: 18%
- NBA présent: 100%

## 5.2 API 8080 + parité frontend
Fichier: `benchmark_api_frontend_parity_100_live.json`
- Notes demandées: 100
- Succès API: 100
- Échecs API: 0
- Durée: 283.21s
- Throughput: 21.19 notes/min
- Qualité moyenne API: 61.95
- Tags moyens API: 12.2
- RAG hit rate API: 90%
- Checks frontend:
  - missing_required_fields: 0
  - invalid_quality_range: 0

## 5.3 Delta pipeline vs API
- Success rate: 100% vs 100%
- Delta qualité moyenne: 1.45
- Delta tags moyens: 0.81
- Delta RAG hit rate: 0.0

Interprétation:
- Le pipeline est stable.
- Le front reçoit une structure cohérente.
- Écart qualité/tags attendu possible selon chemin exact et timing provider.
- Le run API a utilisé majoritairement Tier 2 (96%), alors que le run pipeline direct a escaladé 9 notes en Tier 3.

---

## 6) Tests de validation exécutés

- `python -m pytest -q tests/test_api_auth_enforcement.py tests/test_pipeline_rgpd.py -p no:cacheprovider`
  - 5 passed

- `python -m pytest -q -m "not integration" -p no:cacheprovider`
  - 40 passed, 1 skipped, 2 deselected

- Ciblés ML/Cleaning/RAG (déjà exécutés durant la passe):
  - `tests/test_smart_router_ml_safety.py`
  - `tests/test_text_cleaner.py`
  - `tests/test_pipeline_rag.py`

---

## 7) Features principales (catalogue complet)

## 7.1 Ingestion
- transcription audio via API,
- ingestion batch CSV/XLSX,
- stream de progression pipeline.

## 7.2 Extraction 4 piliers
- Pilier 1: catégories, styles, matériaux, produits matchés RAG.
- Pilier 2: contexte d’achat, profil.
- Pilier 3: allergies, préférences care.
- Pilier 4: action business/NBA, budget, urgence.

## 7.3 Gouvernance qualité
- meta_analysis (quality_score, missing_info, risk_flags),
- feedback advisor,
- dashboard qualité.

## 7.4 Conformité & sécurité
- JWT auth,
- roles advisor/manager,
- RGPD contextualisé,
- anonymisation et fallback local.

## 7.5 Ops & observabilité
- métriques dashboard,
- leaderboard,
- feedback stats,
- composants status (ML router, semantic cache, cross-validator).

---

## 8) Limites actuelles / points à finir pour prod stricte

1. **Secrets**:
- `JWT_SECRET_KEY` doit être défini avec secret fort en environnement de déploiement.

2. **Temps de réponse providers**:
- timeouts Mistral observés ponctuellement (la résilience fonctionne, mais latence variable).
- à monitorer avec alerting SLO.

3. **Base de données**:
- SQLite ok pour dev/PoC.
- migration recommandée vers PostgreSQL pour prod multi-utilisateurs.

4. **CI benchmark régulier**:
- fixer un benchmark qualité 100 notes journalier en CI pour détecter dérive.

5. **Observabilité provider Tier 2**:
- des timeouts Mistral ponctuels ont été observés pendant le benchmark live,
- le circuit breaker protège correctement la pipeline mais il faut monitorer le taux d'ouverture.

---

## 9) Variables d’environnement recommandées

Obligatoires:
- `OPENAI_API_KEY`
- `MISTRAL_API_KEY`
- `JWT_SECRET_KEY`

Optionnelles utiles:
- `GROQ_API_KEY` (non utilisé dans runtime principal actuel)
- `ENABLE_RGPD_LLM=1`
- `RGPD_MODEL=gpt-4o-mini`
- `MAX_CONCURRENT_TIER2_CALLS`
- `MAX_CONCURRENT_TIER3_CALLS`
- `ENABLE_ROUTER_FEEDBACK_LEARNING=1`

---

## 10) Références code

- Entrée API: `api/main.py`
- Auth utils: `api/auth_utils.py`
- Analyze route: `api/routers/analyze.py`
- Transcription route: `api/routers/transcribe.py`
- Pipeline active: `src/pipeline_async.py`
- Router ML: `src/smart_router.py`
- RGPD filter: `src/rgpd_filter.py`
- Recommender: `src/recommender.py`
- RAG matcher: `src/product_matcher.py`
- Modèles de sortie: `src/models.py`
- Legacy rangé: `archive/legacy_groq/`

---

## 11) Conclusion

La pipeline est opérationnelle et cohérente avec un runtime **Mistral + OpenAI**, sans dépendance active à Groq sur le chemin principal.  
La base technique est solide pour la prod, avec trois priorités finales: durcissement secrets, monitoring latence provider, et benchmark qualité en CI.
