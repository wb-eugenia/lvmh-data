# Go Soutenance Checklist - 2026-02-12

## 1) KPI techniques (preuves chiffrees)
- [x] Parite officielle meme runtime prod (`40x1`) >= 90.
  - Run: `benchmark_api_frontend_parity_40_prod_same_runtime_final.json`
  - Resultat: `combined_parity_score_pct = 100.0`
  - Detail: tier `100.0`, rgpd `100.0`, tags `100.0`, success `100.0%`
- [x] Robustesse API prod.
  - Run: `benchmark_api_quality_200_prod_run2_after_deploy.json`
  - Resultat: success `100%`, `http_5xx_count = 0`
- [x] Qualite moyenne prod >= 88.
  - Run: `benchmark_api_quality_200_prod_run2_after_deploy.json`
  - Resultat: `avg_quality_score = 90.02`

## 2) Securite / gouvernance
- [x] Endpoint technique `POST /api/analyze/parity-probe` protege role `manager/admin`.
- [x] Flag de securite `ENABLE_PARITY_PROBE` present et coupe hors campagne.
  - Revision courante: endpoint desactive (`ENABLE_PARITY_PROBE=0`).
- [x] Controle d acces verifie:
  - `advisor -> 403`
  - `manager -> 200` quand flag actif

## 3) Livrables jury
- [x] Deck markdown final: `docs/JURY_DECK_15_SLIDES.md`
- [x] Graphe perf integre: `docs/assets/perf_gain_2026-02-12.svg`
- [x] Captures 4 vues:
  - `docs/assets/ui-captures-2026-02-12/advisor.png`
  - `docs/assets/ui-captures-2026-02-12/manager.png`
  - `docs/assets/ui-captures-2026-02-12/pipeline.png`
  - `docs/assets/ui-captures-2026-02-12/admin.png`
- [x] Dataset demo 20 notes:
  - `data/demo/LVMH_Demo_20_notes_curated.csv`

## 4) Repetition demo
- [x] Script 120s et log x10 prepares:
  - `docs/DEMO_REPETITION_120S.md`

## 5) Artifacts versionnes clefs
- API parity benchmark final:
  - `benchmark_api_frontend_parity_40_prod_same_runtime_final.json`
- API quality prod:
  - `benchmark_api_quality_200_prod_run2_after_deploy.json`
- Rapport execution:
  - `docs/EXECUTION_RESULTS_2026-02-12.md`
