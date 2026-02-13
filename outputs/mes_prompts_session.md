# Mes Prompts - Session LVMH (Chronologique)

Ce fichier regroupe tes prompts de la session, dans l'ordre, en version exploitable.

## 1) Plan features (initial)
Tu as propose un plan complet en 5 features:
- P0: Aho-Corasick Tier1 boost (nouveau moteur ultra rapide, fallback regex, integration router).
- P4: Lexicon auto-generation (YAKE + TF-IDF + clustering, script d'enrichissement taxonomie).
- P1: Clustering post-pipeline (segments analytiques manager).
- P3: Predictions churn/CLV (modele ML + enrichissement NBA).
- P5: Batch mode rapide dedie throughput.

Tu as ajoute:
- Roadmap vendredi/samedi.
- Pitch jury final compare au concurrent.
- Cibles metriques avant/apres.
- Question: "c'est une bonne idee de rajouter ces features ?"

## 2) Prompt d'implementation strict
`PLEASE IMPLEMENT THIS PLAN: Plan All-5 Features Pour Demo Jury (Avec Garde-Fous)`

Tu as impose les garde-fous suivants:
- Garder l'architecture reelle du repo (routing/pipeline existants).
- P1 en segmentation de notes (pas CRM clients complets).
- P3 supervise sur dataset synthetique.
- P4 "review queue only" (pas merge auto en prod).
- P5 dans `/api/batch` existant via `profile=fast_batch`.

Tu as exige:
- Changements API/types/config (batch profile, dashboard segments, champs Pilier4, config match engine).
- Plan implementation detaille P0/P1/P5/P3/P4.
- Plan de tests/non-regression.
- Criteres d'acceptation lundi.
- Hypotheses verrouillees.

## 3) Prompts de pilotage execution
Commandes courtes envoyees:
- `continue`
- `yes go`
- `yes go`
- `fait moi un recap de toutes mes features`
- `depuis le debut faut que ca soit vraiment le recap COMPLET ET EXHAUSTIF`
- `non pas que les features que tu viens de rajouter tout depuis le debut la pipeline le frontend etc.. je te laisse TOUT recuperer`
- `ta mis en prod ?`
- `go`
- `je suis connecte a cloudflare via cli`
- `go`

## 4) Prompt bug frontend React (debug pipeline)
Tu as signale:
- `Minified React error #31`
- Objet rendu invalide avec cles: `{action_type, description, priority, target_products, deadline}`
- Erreur visible en ouvrant des elements du debug pipeline.
- Repro sur build prod frontend (fichiers vendor minifies).

Prompt associe:
- `fix`
- Puis confirmation: `oui`
- Puis relance: `encore ca c'est quand j'ouvre des truc dans debug pipeline`

## 5) Prompt audit bugs critiques (compte-rendu detaille)
Tu as fourni un rapport structure:
- Quality score affiche 9184% (au lieu ~75-85/100 attendu).
- Confiance extraction affichee 0% (attendu ~91-95%).
- Completude 0% (alors que la note contient budget/produit/occasion/allergie/RDV).
- Header tags incoherent (0 vs tags visibles).
- Latence API elevee sur run (8852ms).
- Warnings faux ("budget non specifie").
- NBA partiellement hors sujet.
- RAG produits hors sujet (livre/pantalon alors que intention sac Capucines).

Tu as aussi donne:
- Priorites fixes P0/P1/P2 avec snippets.
- Resultats attendus apres fix.
- Timing 1h avant call.
- Consigne: priorite absolue quality/confiance/completude.

## 6) Prompt de correction contextualise (debug vs vue principale)
Tu as precise:
- Vue principale/historique correcte (quality 92%, confiance 95%).
- Debug pipeline bugué sur affichage (quality 9184%, confiance 0%, tags count faux).
- Completude 0% reste un bug backend commun.
- Budget "N/A" + "8000€" incoherent en affichage.
- RAG encore hors sujet.
- NBA manque actions contextuelles.

Tu as fixe un plan 30 min:
- Sync affichage DebugAnalyzer avec vue principale.
- Corriger calcul completude backend.
- Ajouter logs RAG et filtrage categorie/couleur.

## 7) Prompt final (cette demande)
- `fait moi un md ou ya mes prompts`

## 8) Templates reutilisables (copier-coller)
### Template A - Implementation globale
```text
PLEASE IMPLEMENT THIS PLAN:
- P0 Aho Tier1 dans pipeline existant + fallback regex
- P1 segmentation notes + endpoint dashboard + UI manager
- P5 profile=fast_batch dans /api/batch existant
- P3 churn/CLV synthetique + enrichissement NBA + mention source=synthetic
- P4 lexicon review queue only (pas merge auto taxonomie prod)
Avec tests de parite, perf, non-regression et compatibilite schema API.
```

### Template B - Fix debug frontend
```text
Fix React error #31 in DebugAnalyzer:
- Ne jamais rendre un objet brut dans JSX
- Mapper NBA object -> texte lisible
- Aligner quality/confidence/tags display avec AdvisorView
- Ajouter fallback robustes si champs absents
```

### Template C - Stabilisation metriques demo
```text
Corrige en priorite:
1) quality display (pas de double *100)
2) avg_extraction_confidence mapping
3) completeness backend calc
4) tags count global
Puis verifie RAG pertinence produits + enrichissement NBA contextuel.
```

