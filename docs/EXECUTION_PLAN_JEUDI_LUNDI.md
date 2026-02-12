# Plan Execution Jeudi -> Lundi (Sans 100x3)

## Cibles verrouillees
- Parite jeudi: `combined_parity_score_pct >= 90` sur `40 notes x1`.
- Qualite vendredi: `avg_quality_score >= 88` sur `100 notes x1`.
- Robustesse API vendredi: `200 notes`, `runs=1`.
- E2E advisor: flux texte deterministe (sans micro CI).

## Ce qui est deja implemente
- Script parite etendu:
  - `--pipeline-profile` (default `single_note`)
  - `--weights-tier`, `--weights-rgpd`, `--weights-tags`
  - `combined_parity_score_pct`
  - rapport `per_note_diff` avec `tier_mismatch`, `rgpd_mismatch`, `low_tag_jaccard`.
- Normalisation frontend centralisee:
  - `frontend-v2/src/lib/api.js` -> `normalizeAnalysisResult()`
  - Consommateurs alignes:
    - `frontend-v2/src/components/AdvisorView.jsx`
    - `frontend-v2/src/components/ManagerView.jsx`
- Stabilite types API:
  - `api/schemas.py`: validators pour `tier`, `contains_sensitive`, `tags`.
  - `api/routers/analyze.py`: coercion defensive + preservation des `HTTPException`.
- E2E socle pret:
  - `frontend-v2/playwright.config.ts`
  - `frontend-v2/tests/e2e/advisor-text-flow.spec.ts`
  - `frontend-v2/package.json` scripts `e2e`.
- UX deterministic mode:
  - bouton `Mode texte (deterministe)` dans `AdvisorView`.
- Deck jury:
  - source markdown 15 slides: `docs/JURY_DECK_15_SLIDES.md`
  - export helper PDF: `scripts/export_jury_deck_pdf.ps1`.

## Commandes execution (sans charge 100x3)

### Jeudi - Parite 40x1
```bash
python scripts/benchmark_api_frontend_parity.py \
  --limit 40 \
  --pipeline-profile single_note \
  --weights-tier 0.4 \
  --weights-rgpd 0.4 \
  --weights-tags 0.2 \
  --output-json benchmark_api_frontend_parity_40_single_note.json
```

### Vendredi - API 200x1
```bash
python scripts/benchmark_api_quality.py --limit 200 --runs 1
```

### Vendredi - Qualite 100x1
```bash
python scripts/benchmark_quality_pipeline.py --limit 100
```

### Vendredi - E2E advisor deterministic
```bash
cd frontend-v2
npm run e2e -- --project=chromium
```

## Livrables jury
- Deck markdown: `docs/JURY_DECK_15_SLIDES.md`
- Export PDF:
```powershell
./scripts/export_jury_deck_pdf.ps1
```

## Reste a faire
- Executer les campagnes 40x1 / 200x1 / 100x1 (non lancees ici).
- Corriger les 3 causes majoritaires de mismatch issues du `per_note_diff`.
- Integrer graphe perf final + captures 4 vues dans le deck PDF.
- Constituer dataset demo 20 notes scenarios VIP/allergies/Capucines.
- Repetition demo 120s x10 + Q&A jury.
