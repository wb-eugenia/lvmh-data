# Demo 120s - Script et Log Repetition

## Script cible (120 secondes)
1. 0s-15s: Login advisor (`advisor@lvmh.com`) et ouverture vue advisor.
2. 15s-45s: Analyse note demo (mode texte deterministe), afficher tags + RGPD + NBA.
3. 45s-75s: Basculer vue manager, montrer opportunite prioritaire et action manager.
4. 75s-95s: Basculer vue pipeline `/pipeline`, afficher monitoring live.
5. 95s-115s: Basculer vue admin, montrer couts, latence, alertes.
6. 115s-120s: Conclusion ROI + conformite RGPD.

## Messages cle jury
- Gain vitesse: ~41% sur temps moyen note.
- Qualite prod: score moyen >= 90 (run de reference).
- Parite officielle meme runtime prod: >= 90 (run `40x1`).
- Gouvernance: RBAC advisor/manager/admin + endpoint technique protege et coupe hors campagne.

## Log repetitions (x10)
| Run | Duree (s) | Blocage observe | Correctif applique | Pret jury |
|---|---:|---|---|---|
| 1 | 14.29 | Aucun | N/A | Oui |
| 2 | 12.66 | Aucun | N/A | Oui |
| 3 | 12.63 | Aucun | N/A | Oui |
| 4 | 12.81 | Aucun | N/A | Oui |
| 5 | 12.53 | Aucun | N/A | Oui |
| 6 | 13.13 | Aucun | N/A | Oui |
| 7 | 13.63 | Aucun | N/A | Oui |
| 8 | 12.59 | Aucun | N/A | Oui |
| 9 | 12.94 | Aucun | N/A | Oui |
| 10 | 13.21 | Aucun | N/A | Oui |

Source runs:
- Playwright repeated run (`repeat-each=10`, `workers=1`) on `tests/e2e/capture-views.spec.ts`
- Report file: `output/demo_repetition_runs_2026-02-12.json`
