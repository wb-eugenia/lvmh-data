# Plan d'Intégration BigQuery Streaming - LVMH Data

> **Date**: 16 février 2026
> **Statut**: Planifié
> **Temps estimé**: 5-7 heures

---

## Contexte

LVMH Data Pipeline V2.3 est actuellement en production avec:
- **Frontend**: Cloudflare Pages (https://lvmh-frontend.pages.dev)
- **API**: GCP Cloud Run (https://lvmh-api-570069708764.europe-west9.run.app)
- **Base de données**: SQLite locale
- **Métriques**: Fichiers CSV locaux (`logs/cost_metrics.csv`)

L'intégration BigQuery permettra:
- Dashboard temps réel avec Looker Studio
- Analyse cross-boutique
- Historique illimité
- Requêtes ad-hoc performantes

---

## État Actuel du Code

### Client BigQuery Existant
- **Fichier**: `src/bigquery_client.py`
- **Statut**: Développé mais non intégré à l'API
- **Fonctionnalités**:
  - Streaming insert basique
  - Schéma simple (note_id, timestamp, tags, etc.)
  - Gestion d'erreurs

### Ce qui Manque
- ❌ Configuration dans `config/production.py`
- ❌ Initialisation au startup de l'API
- ❌ Intégration dans les routers (`batch.py`, `analyze.py`)
- ❌ Schéma étendu avec 4 piliers
- ❌ Table d'agrégats pour dashboards
- ❌ Dashboards Looker Studio

---

## Phase 1: Configuration GCP (30 min)

### 1.1 Prérequis
```bash
# Installer le SDK Google Cloud
brew install google-cloud-sdk

# Ou pip
pip install google-cloud-bigquery
```

### 1.2 Configuration Console GCP

| Étape | Action |
|-------|--------|
| 1 | Créer projet GCP (ou utiliser existant) |
| 2 | Activer **BigQuery API** |
| 3 | Créer **Service Account** avec rôle `BigQuery Data Editor` |
| 4 | Générer clé JSON credentials |
| 5 | Télécharger le fichier `credentials.json` |

### 1.3 Variables d'Environnement

```bash
# .env
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
BIGQUERY_DATASET=lvmh_data
BIGQUERY_TABLE=notes
BIGQUERY_ENABLED=true
```

---

## Phase 2: Schéma BigQuery

### 2.1 Table Principale: Notes

```sql
CREATE TABLE `{project}.lvmh_data.notes`
(
  -- Identifiants
  note_id STRING NOT NULL,
  timestamp TIMESTAMP NOT NULL,
  store_id STRING,
  advisor_id STRING,
  
  -- Métriques processing
  tier_used INT64 NOT NULL,
  processing_time_ms FLOAT,
  cost_usd FLOAT,
  confidence_score FLOAT,
  quality_score FLOAT,
  points_awarded INT64,
  
  -- Tags extraits
  tags ARRAY<STRING>,
  budget_range STRING,
  client_status STRING,
  urgency STRING,
  
  -- Flags
  has_risk_flag BOOL,
  is_vic BOOL,
  
  -- Pilier 1: Univers Produit
  pilier_1_category STRING,
  pilier_1_style STRING,
  pilier_1_color STRING,
  pilier_1_material STRING,
  pilier_1_brand STRING,
  
  -- Pilier 2: Profil Client
  pilier_2_purchase_context STRING,
  pilier_2_socio_pro STRING,
  pilier_2_interests ARRAY<STRING>,
  pilier_2_vic_status STRING,
  
  -- Pilier 3: Hospitalité & Care
  pilier_3_occasion STRING,
  pilier_3_allergies ARRAY<STRING>,
  pilier_3_preferences ARRAY<STRING>,
  
  -- Pilier 4: Action Business
  pilier_4_nba STRING,
  pilier_4_urgency STRING,
  pilier_4_budget_potential FLOAT,
  
  -- Métadonnées
  original_text_length INT64,
  processed_text_length INT64,
  cache_hit BOOL
)
PARTITION BY DATE(timestamp)
CLUSTER BY store_id, advisor_id
OPTIONS(
  description="LVMH Data - Notes tagguees en temps reel",
  labels=[("env", "production")]
);
```

### 2.2 Table Agrégats: Métriques Quotidiennes

```sql
CREATE TABLE `{project}.lvmh_data.daily_metrics`
PARTITION BY date
AS SELECT
  DATE(timestamp) as date,
  store_id,
  COUNT(*) as note_count,
  AVG(confidence_score) as avg_confidence,
  AVG(quality_score) as avg_quality,
  AVG(processing_time_ms) as avg_processing_ms,
  SUM(cost_usd) as total_cost,
  SUM(points_awarded) as total_points,
  COUNTIF(is_vic) as vic_count,
  COUNTIF(tier_used = 1) as tier1_count,
  COUNTIF(tier_used = 2) as tier2_count,
  COUNTIF(tier_used = 3) as tier3_count,
  COUNTIF(cache_hit = true) as cache_hits
FROM `{project}.lvmh_data.notes`
GROUP BY 1, 2;
```

### 2.3 Table: Advisor Performance

```sql
CREATE TABLE `{project}.lvmh_data.advisor_metrics`
PARTITION BY date
AS SELECT
  DATE(timestamp) as date,
  advisor_id,
  store_id,
  COUNT(*) as notes_count,
  SUM(points_awarded) as total_points,
  AVG(quality_score) as avg_quality_score,
  COUNTIF(is_vic = true) as vic_served
FROM `{project}.lvmh_data.notes`
GROUP BY 1, 2, 3;
```

---

## Phase 3: Intégration Code

### 3.1 Configuration (`config/production.py`)

Ajouter les paramètres suivants:

```python
class Settings(BaseModel):
    # ... existing fields ...
    
    # BigQuery Configuration
    bigquery_enabled: bool = Field(default=False)
    bigquery_project_id: str = Field(default_factory=lambda: os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    bigquery_dataset: str = Field(default="lvmh_data")
    bigquery_table: str = Field(default="notes")
    bigquery_credentials_path: str = Field(default_factory=lambda: os.getenv("GOOGLE_APPLICATION_CREDENTIALS", ""))
```

### 3.2 Client BigQuery Amélioré (`src/bigquery_client.py`)

Améliorations nécessaires:

```python
class BigQueryManager:
    """Gestionnaire BigQuery avec schéma 4-piliers"""
    
    SCHEMA = [
        # ... existing fields ...
        
        # Pilier 1
        bigquery.SchemaField("pilier_1_category", "STRING"),
        bigquery.SchemaField("pilier_1_style", "STRING"),
        bigquery.SchemaField("pilier_1_color", "STRING"),
        bigquery.SchemaField("pilier_1_material", "STRING"),
        bigquery.SchemaField("pilier_1_brand", "STRING"),
        
        # Pilier 2
        bigquery.SchemaField("pilier_2_purchase_context", "STRING"),
        bigquery.SchemaField("pilier_2_socio_pro", "STRING"),
        bigquery.SchemaField("pilier_2_interests", "STRING", mode="REPEATED"),
        bigquery.SchemaField("pilier_2_vic_status", "STRING"),
        
        # Pilier 3
        bigquery.SchemaField("pilier_3_occasion", "STRING"),
        bigquery.SchemaField("pilier_3_allergies", "STRING", mode="REPEATED"),
        bigquery.SchemaField("pilier_3_preferences", "STRING", mode="REPEATED"),
        
        # Pilier 4
        bigquery.SchemaField("pilier_4_nba", "STRING"),
        bigquery.SchemaField("pilier_4_urgency", "STRING"),
        bigquery.SchemaField("pilier_4_budget_potential", "FLOAT"),
        
        # Métadonnées
        bigquery.SchemaField("original_text_length", "INT64"),
        bigquery.SchemaField("processed_text_length", "INT64"),
        bigquery.SchemaField("cache_hit", "BOOL"),
    ]
    
    def transform_result_to_row(self, result: dict) -> dict:
        """Transforme le résultat du pipeline en row BQ"""
        ext = result.get("extraction", {})
        pilier1 = ext.get("pilier_1_univers_produit", {})
        pilier2 = ext.get("pilier_2_profil_client", {})
        pilier3 = ext.get("pilier_3_hospitalite_care", {})
        pilier4 = ext.get("pilier_4_action_business", {})
        
        return {
            "note_id": result.get("id"),
            "timestamp": datetime.now().isoformat(),
            "store_id": result.get("metadata", {}).get("store_id"),
            "advisor_id": result.get("metadata", {}).get("advisor_id"),
            
            "tier_used": result.get("routing", {}).get("tier", 1),
            "processing_time_ms": result.get("processing_time_ms", 0),
            "cost_usd": result.get("cost", 0),
            "confidence_score": result.get("meta_analysis", {}).get("confidence_score", 0),
            "quality_score": result.get("meta_analysis", {}).get("quality_score", 0),
            "points_awarded": result.get("points_awarded", 0),
            
            "tags": result.get("tags", []),
            "budget_range": ext.get("budget_range"),
            "client_status": pilier2.get("purchase_context"),
            "urgency": pilier4.get("urgency"),
            
            "has_risk_flag": len(result.get("rgpd", {}).get("risk_flags", [])) > 0,
            "is_vic": "vic" in (pilier2.get("vip_status") or "").lower(),
            
            # Pilier 1
            "pilier_1_category": pilier1.get("category"),
            "pilier_1_style": pilier1.get("style"),
            "pilier_1_color": pilier1.get("color"),
            "pilier_1_material": pilier1.get("material"),
            "pilier_1_brand": pilier1.get("brand"),
            
            # Pilier 2
            "pilier_2_purchase_context": pilier2.get("purchase_context"),
            "pilier_2_socio_pro": pilier2.get("socio_pro"),
            "pilier_2_interests": pilier2.get("interests", []),
            "pilier_2_vic_status": pilier2.get("vip_status"),
            
            # Pilier 3
            "pilier_3_occasion": pilier3.get("occasion"),
            "pilier_3_allergies": pilier3.get("allergies", []),
            "pilier_3_preferences": pilier3.get("preferences", []),
            
            # Pilier 4
            "pilier_4_nba": pilier4.get("nba"),
            "pilier_4_urgency": pilier4.get("urgency"),
            "pilier_4_budget_potential": pilier4.get("budget_potential"),
            
            # Métadonnées
            "original_text_length": len(result.get("original_text", "")),
            "processed_text_length": len(result.get("processed_text", "")),
            "cache_hit": result.get("cache_hit", False),
        }
```

### 3.3 Intégration API (`api/main.py`)

```python
# Au startup
from src.bigquery_client import BigQueryManager

@app.on_event("startup")
async def startup_bigquery():
    if settings.bigquery_enabled:
        app.state.bq_manager = BigQueryManager(
            project_id=settings.bigquery_project_id,
            dataset_id=settings.bigquery_dataset,
            table_id=settings.bigquery_table
        )
        logger.info("BigQuery manager initialized")
```

### 3.4 Intégration Batch Router (`api/routers/batch.py`)

```python
# Après traitement du batch
if hasattr(app.state, "bq_manager") and app.state.bq_manager:
    rows = [app.state.bq_manager.transform_result_to_row(r) for r in results]
    app.state.bq_manager.insert_rows(rows)
```

---

## Phase 4: Looker Studio Dashboards

### 4.1 Dashboard: Overview

| Métrique | Requête BigQuery |
|----------|-----------------|
| Notes/jour | `SELECT date, COUNT(*) FROM daily_metrics GROUP BY date` |
| Confidence moyenne | `SELECT date, AVG(avg_confidence) FROM daily_metrics` |
| Coût total | `SELECT date, SUM(total_cost) FROM daily_metrics` |
| Taux VIC | `SELECT date, SUM(vic_count)/SUM(note_count) FROM daily_metrics` |

### 4.2 Dashboard: Produits

| Métrique | Description |
|----------|-------------|
| Top catégories | Tags pilier_1_category |
| Top couleurs | Tags pilier_1_color |
| Top styles | Tags pilier_1_style |
| Tendances | Comparaison semaine glissante |

### 4.3 Dashboard: Advisors

| Métrique | Source |
|----------|--------|
| Leaderboard points | `advisor_metrics` |
| Quality score moyen | `AVG(avg_quality_score)` |
| Notes par advisor | `SUM(notes_count)` |
| VIC servis | `SUM(vic_served)` |

### 4.4 Dashboard: VIC Analysis

Filtres:
- `is_vic = true`
- Comparaison comportement VIC vs Standard

Métriques:
- Budget potentiel moyen
- Occasions fréquentes
- Produits demandés

### 4.5 Dashboard: Costs

| Métrique | Calcul |
|----------|--------|
| Coût par tier | `SUM(cost) GROUP BY tier` |
| Projection mensuelle | `AVG(daily_cost) * 30` |
| Coût par note | `SUM(total_cost) / SUM(note_count)` |

---

## Coûts Estimés

### Paramètres
- **Volume**: ~500 notes/jour (estimé)
- **Taille moyenne**: ~5-10 KB/note

### Coûts Mensuels

| Composant | Prix | Estimation |
|-----------|------|------------|
| Stockage | $0.02/GB | ~$0.01/mois |
| Streaming Insert | $0.01/200MB | ~$0.10/mois |
| Queries (50/jour) | $5/TB | ~$10-20/mois |

**Total estimé: $15-30/mois**

### Optimisations
- Partitionnement par date (réduit coûts query)
- Materialized views pour dashboards fréquents
- Scheduled queries pour agrégats nocturnes

---

## Checklist d'Implémentation

### Week 1
- [ ] Setup GCP + Service Account
- [ ] Activer BigQuery API
- [ ] Créer tables (notes, daily_metrics, advisor_metrics)
- [ ] Configurer variables d'environnement

### Week 2
- [ ] Enrichir `src/bigquery_client.py` avec schéma 4-piliers
- [ ] Ajouter config dans `config/production.py`
- [ ] Intégrer dans `api/main.py`
- [ ] Intégrer dans `api/routers/batch.py`

### Week 3
- [ ] Looker Studio: Dashboard Overview
- [ ] Looker Studio: Dashboard Produits
- [ ] Looker Studio: Dashboard Advisors
- [ ] Looker Studio: Dashboard VIC

### Week 4 (Optionnel)
- [ ] Alertes automatiques (coût, qualité)
- [ ] Scheduled queries pour agrégats
- [ ] Monitoring dashboard

---

## Phase 4: Looker Studio Dashboards

### 4.1 Accès à Looker Studio

1. Aller sur https://lookerstudio.google.com
2. Se connecter avec le compte Google
3. Cliquer sur **"Create"** → **"Data Source"**

### 4.2 Connecter BigQuery

1. Sélectionner **Google BigQuery** comme source
2. Choisir le projet: `elite-hold-485510-t5`
3. Dataset: `lvmh_data`
4. Table: Au choix selon le dashboard

---

### 4.3 Dashboard: Overview

**Source:** `lvmh_data.daily_metrics`

| Métrique | Requête BigQuery |
|----------|-----------------|
| Notes/jour | `SELECT date, note_count FROM daily_metrics ORDER BY date DESC LIMIT 30` |
| Confidence | `SELECT date, avg_confidence FROM daily_metrics` |
| Coût total | `SELECT SUM(total_cost) FROM daily_metrics` |
| Taux VIC | `SELECT SUM(vic_count)/SUM(note_count) FROM daily_metrics` |

**Visualisations:**
- Line chart: Notes par jour (30 derniers jours)
- Score card: Total notes, Avg confidence, Total cost
- Pie chart: Distribution tier (tier1 vs tier2 vs tier3)

---

### 4.4 Dashboard: Produits

**Source:** `lvmh_data.notes`

**Requêtes utiles:**
```sql
-- Top catégories
SELECT pilier_1_category, COUNT(*) as cnt
FROM `elite-hold-485510-t5.lvmh_data.notes`
WHERE pilier_1_category IS NOT NULL
GROUP BY 1 ORDER BY 2 DESC LIMIT 10

-- Top couleurs
SELECT pilier_1_color, COUNT(*) as cnt
FROM `elite-hold-485510-t5.lvmh_data.notes`
WHERE pilier_1_color IS NOT NULL
GROUP BY 1 ORDER BY 2 DESC LIMIT 10

-- Top styles
SELECT pilier_1_style, COUNT(*) as cnt
FROM `elite-hold-485510-t5.lvmh_data.notes`
WHERE pilier_1_style IS NOT NULL
GROUP BY 1 ORDER BY 2 DESC LIMIT 10
```

---

### 4.5 Dashboard: Advisors `lvmh

**Source:**_data.advisor_metrics`

| Métrique | Requête |
|----------|---------|
| Leaderboard | `SELECT advisor_id, SUM(total_points) as pts FROM advisor_metrics GROUP BY 1 ORDER BY 2 DESC` |
| Quality score | `SELECT advisor_id, AVG(avg_quality_score) as avg_q FROM advisor_metrics GROUP BY 1` |
| VIC servis | `SELECT advisor_id, SUM(vic_served) FROM advisor_metrics GROUP BY 1` |

---

### 4.6 Dashboard: VIC Analysis

**Source:** `lvmh_data.notes`

Filtres recommandés:
- `is_vic = true`

Métriques:
- Budget potentiel moyen par VIC
- Occasions fréquentes (anniversaires, Noël)
- Produits demandés par les VIC

---

### 4.7 Dashboard: Coûts

**Source:** `lvmh_data.daily_metrics`

| Métrique | Calcul |
|----------|--------|
| Coût par tier | `SELECT tier, SUM(cost) FROM notes GROUP BY tier` |
| Projection mensuelle | `AVG(daily_cost) * 30` |
| Coût par note | `SUM(total_cost) / SUM(note_count)` |

---

## Commandes Utiles

### Refresh manuel des tables agrégées
```bash
python scripts/bigquery_refresh.py
```

### Vérifier les données
```python
from google.cloud import bigquery
client = bigquery.Client(project='elite-hold-485510-t5')

# Compter les lignes
query = 'SELECT COUNT(*) FROM `elite-hold-485510-t5.lvmh_data.notes`'
print(list(client.query(query).result())[0][0])
```

---

## Ressources

### Liens Utiles
- [BigQuery Pricing](https://cloud.google.com/bigquery/pricing)
- [Looker Studio](https://lookerstudio.google.com)
- [BigQuery Python Client](https://google-cloud-python.readthedocs.io/en/latest/bigquery/usage.html)

### Fichiers du Projet
- Client existant: `src/bigquery_client.py`
- Configuration: `config/production.py`
- Batch router: `api/routers/batch.py`
- Main API: `api/main.py`

---

## Questions Ouvertes

1. **Volume**: Combien de notes par jour est prévu ?
2. **Rétrocompatibilité**: Envoyer les notes historiques (backfill) ?
3. **Dashboard**: Priorité sur quels dashboards ?
4. **Alertes**: Vouloir des notifications (coût, qualité) ?

---

*Document généré automatiquement - LVMH Data Office*
