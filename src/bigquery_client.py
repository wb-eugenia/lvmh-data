"""
Google BigQuery Client
Handles streaming data insertion for LVMH Pipeline results.
"""

import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

try:
    from google.cloud import bigquery
    from google.api_core.exceptions import GoogleAPIError
    HAS_BQ = True
except ImportError:
    HAS_BQ = False
    bigquery = None

logger = logging.getLogger(__name__)


class BigQueryManager:
    """
    Gestionnaire d'export vers Google BigQuery.
    Schema-aware avec support 4-pilliers et résilient.
    """
    
    SCHEMA = [
        # Identifiants
        bigquery.SchemaField("note_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("store_id", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("advisor_id", "STRING", mode="NULLABLE"),
        
        # Métriques processing
        bigquery.SchemaField("tier_used", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("processing_time_ms", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("cost_usd", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("confidence_score", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("quality_score", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("points_awarded", "INTEGER", mode="NULLABLE"),
        
        # Tags extraits
        bigquery.SchemaField("tags", "STRING", mode="REPEATED"),
        bigquery.SchemaField("budget_range", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("client_status", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("urgency", "STRING", mode="NULLABLE"),
        
        # Flags
        bigquery.SchemaField("has_risk_flag", "BOOLEAN", mode="NULLABLE"),
        bigquery.SchemaField("is_vic", "BOOLEAN", mode="NULLABLE"),
        
        # Pilier 1: Univers Produit
        bigquery.SchemaField("pilier_1_category", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("pilier_1_style", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("pilier_1_color", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("pilier_1_material", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("pilier_1_brand", "STRING", mode="NULLABLE"),
        
        # Pilier 2: Profil Client
        bigquery.SchemaField("pilier_2_purchase_context", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("pilier_2_socio_pro", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("pilier_2_interests", "STRING", mode="REPEATED"),
        bigquery.SchemaField("pilier_2_vic_status", "STRING", mode="NULLABLE"),
        
        # Pilier 3: Hospitalité & Care
        bigquery.SchemaField("pilier_3_occasion", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("pilier_3_allergies", "STRING", mode="REPEATED"),
        bigquery.SchemaField("pilier_3_preferences", "STRING", mode="REPEATED"),
        
        # Pilier 4: Action Business
        bigquery.SchemaField("pilier_4_nba", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("pilier_4_urgency", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("pilier_4_budget_potential", "FLOAT", mode="NULLABLE"),
        
        # Métadonnées
        bigquery.SchemaField("original_text_length", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("processed_text_length", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("cache_hit", "BOOLEAN", mode="NULLABLE"),
    ] if HAS_BQ else []

    def __init__(self, project_id: str = None, dataset_id: str = "lvmh_data", table_id: str = "notes"):
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.dataset_id = dataset_id
        self.table_id = table_id
        
        self.enabled = HAS_BQ and bool(self.project_id)
        
        if not self.enabled:
            if not HAS_BQ:
                logger.warning("Google Cloud BigQuery not installed. Run `pip install google-cloud-bigquery`.")
            else:
                logger.warning("No Google Cloud Project ID found. BigQuery export disabled.")
            self.client = None
            return

        try:
            self.client = bigquery.Client(project=self.project_id)
            self.dataset_ref = self.client.dataset(self.dataset_id)
            self.table_ref = self.dataset_ref.table(self.table_id)
            
            # Verify connection
            self.client.get_dataset(self.dataset_ref)
            logger.info(f"Connected to BigQuery: {self.project_id}.{self.dataset_id}")
        except Exception as e:
            logger.error(f"BigQuery connection failed: {e}")
            self.enabled = False
            self.client = None

    def transform_result_to_row(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Transforme le résultat du pipeline en row BigQuery"""
        
        # Extraction des données imbriquées
        ext = result.get("extraction", {})
        routing = result.get("routing", {})
        meta = result.get("meta_analysis", {})
        rgpd = result.get("rgpd", {})
        
        # Piliers
        pilier1 = ext.get("pilier_1_univers_produit", {})
        pilier2 = ext.get("pilier_2_profil_client", {})
        pilier3 = ext.get("pilier_3_hospitalite_care", {})
        pilier4 = ext.get("pilier_4_action_business", {})
        
        # Tags extraction
        tags = result.get("tags", [])
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except:
                tags = []
        
        return {
            "note_id": result.get("id", f"note-{datetime.now().timestamp()}"),
            "timestamp": datetime.now().isoformat(),
            "store_id": result.get("metadata", {}).get("store_id"),
            "advisor_id": result.get("metadata", {}).get("advisor_id"),
            
            # Métriques
            "tier_used": routing.get("tier", 1),
            "processing_time_ms": result.get("processing_time_ms", 0) or 0,
            "cost_usd": result.get("cost", 0) or 0,
            "confidence_score": meta.get("confidence_score", 0) or 0,
            "quality_score": meta.get("quality_score", 0) or 0,
            "points_awarded": result.get("points_awarded", 0) or 0,
            
            # Tags
            "tags": tags,
            "budget_range": ext.get("budget_range"),
            "client_status": ext.get("client_status"),
            "urgency": pilier4.get("urgency"),
            
            # Flags
            "has_risk_flag": rgpd.get("contains_sensitive", False) or len(rgpd.get("risk_flags", [])) > 0,
            "is_vic": "vic" in (pilier2.get("vip_status") or "").lower(),
            
            # Pilier 1: Univers Produit
            "pilier_1_category": pilier1.get("category"),
            "pilier_1_style": pilier1.get("style"),
            "pilier_1_color": pilier1.get("color"),
            "pilier_1_material": pilier1.get("material"),
            "pilier_1_brand": pilier1.get("brand"),
            
            # Pilier 2: Profil Client
            "pilier_2_purchase_context": pilier2.get("purchase_context"),
            "pilier_2_socio_pro": pilier2.get("socio_pro"),
            "pilier_2_interests": pilier2.get("interests", []),
            "pilier_2_vic_status": pilier2.get("vip_status"),
            
            # Pilier 3: Hospitalité
            "pilier_3_occasion": pilier3.get("occasion"),
            "pilier_3_allergies": pilier3.get("allergies", []),
            "pilier_3_preferences": pilier3.get("preferences", []),
            
            # Pilier 4: Action Business
            "pilier_4_nba": pilier4.get("nba"),
            "pilier_4_urgency": pilier4.get("urgency"),
            "pilier_4_budget_potential": pilier4.get("budget_potential"),
            
            # Métadonnées
            "original_text_length": len(result.get("original_text", "")) if result.get("original_text") else 0,
            "processed_text_length": len(result.get("processed_text", "")) if result.get("processed_text") else 0,
            "cache_hit": result.get("cache_hit", False) or False,
        }

    def insert_rows(self, results: List[Dict[str, Any]]) -> bool:
        """Stream insert rows into BigQuery."""
        if not self.enabled or not results or not self.client:
            return False
        
        rows_to_insert = []
        for res in results:
            row = self.transform_result_to_row(res)
            rows_to_insert.append(row)

        try:
            errors = self.client.insert_rows_json(self.table_ref, rows_to_insert)
            if errors == []:
                logger.info(f"Streamed {len(rows_to_insert)} rows to BigQuery")
                return True
            else:
                logger.error(f"BigQuery Insert Errors: {errors}")
                return False
        except Exception as e:
            logger.error(f"BigQuery Critical Error: {e}")
            return False

    def create_dataset_if_not_exists(self) -> bool:
        """Crée le dataset si inexistant"""
        if not self.enabled or not self.client:
            return False
        
        try:
            self.client.get_dataset(self.dataset_ref)
            logger.info(f"Dataset {self.dataset_id} already exists")
            return True
        except Exception:
            dataset = bigquery.Dataset(self.dataset_ref)
            dataset.location = "EU"
            dataset.description = "LVMH Data warehouse"
            self.client.create_dataset(dataset)
            logger.info(f"Created dataset: {self.dataset_id}")
            return True

    def create_table_if_not_exists(self) -> bool:
        """Crée la table si inexistante"""
        if not self.enabled or not self.client:
            return False
        
        try:
            self.client.get_table(self.table_ref)
            logger.info(f"Table {self.table_id} already exists")
            return True
        except Exception:
            table = bigquery.Table(self.table_ref, schema=self.SCHEMA)
            table.time_partitioning = bigquery.TimePartitioning(
                type_=bigquery.TimePartitioningType.DAY,
                field="timestamp"
            )
            table.clustering_fields = ["store_id", "advisor_id"]
            self.client.create_table(table)
            logger.info(f"Created table: {self.table_id}")
            return True
