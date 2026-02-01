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

logger = logging.getLogger(__name__)

class BigQueryManager:
    """
    Gestionnaire d'export vers Google BigQuery.
    Schema-aware et résilient.
    """
    
    # Schéma de table cible (pour création automatique si besoin)
    SCHEMA = [
        bigquery.SchemaField("note_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("store_id", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("advisor_id", "STRING", mode="NULLABLE"),
        
        # Core Analysis
        bigquery.SchemaField("tier_used", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("processing_time_ms", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("cost_usd", "FLOAT", mode="NULLABLE"),
        bigquery.SchemaField("confidence_score", "FLOAT", mode="NULLABLE"),
        
        # Extracted Data (Nested)
        bigquery.SchemaField("tags", "STRING", mode="REPEATED"),
        bigquery.SchemaField("budget_range", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("client_status", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("urgency", "STRING", mode="NULLABLE"),
        
        # Computed
        bigquery.SchemaField("has_risk_flag", "BOOLEAN", mode="NULLABLE"),
        bigquery.SchemaField("is_vic", "BOOLEAN", mode="NULLABLE"),
    ] if HAS_BQ else []

    def __init__(self, project_id: str = None, dataset_id: str = "lvmh_voice_data", table_id: str = "notes_tagged"):
        self.enabled = HAS_BQ and (project_id or os.getenv("GOOGLE_CLOUD_PROJECT"))
        
        if not self.enabled:
            if not HAS_BQ:
                logger.warning("🚫 Google Cloud BigQuery not installed. Run `pip install google-cloud-bigquery`.")
            else:
                logger.warning("🚫 No Google Cloud Project ID found. BigQuery export disabled.")
            return

        self.client = bigquery.Client(project=project_id)
        self.dataset_ref = self.client.dataset(dataset_id)
        self.table_ref = self.dataset_ref.table(table_id)
        
        # Check connection
        try:
            self.client.get_dataset(self.dataset_ref)
            logger.info(f"✅ Connected to BigQuery: {project_id}.{dataset_id}")
        except Exception as e:
            logger.error(f"❌ BigQuery Dataset not found or accessible: {e}")
            self.enabled = False

    def insert_rows(self, results: List[Dict[str, Any]]) -> bool:
        """
        Stream insert rows into BigQuery.
        Transforme les objets Python complexes en format BQ-compatible.
        """
        if not self.enabled or not results:
            return False
            
        rows_to_insert = []
        for res in results:
            # Flatten / Normalize for BQ
            row = {
                "note_id": res.get("id", f"unknown-{datetime.now().timestamp()}"),
                "timestamp": datetime.now().isoformat(),
                "store_id": res.get("metadata", {}).get("store_id"),
                "advisor_id": res.get("metadata", {}).get("advisor_id"),
                
                "tier_used": res.get("tier", 0),
                "processing_time_ms": res.get("processing_time", 0.0),
                "cost_usd": res.get("cost", 0.0),
                "confidence_score": res.get("confidence", 0.0),
                
                "tags": res.get("result", {}).get("tags", []),
                "budget_range": res.get("result", {}).get("budget_range"),
                "client_status": res.get("result", {}).get("client_status"),
                "urgency": res.get("result", {}).get("urgency"),
                
                "has_risk_flag": len(res.get("result", {}).get("risk_flags", {})) > 0,
                "is_vic": "vic" in (res.get("result", {}).get("client_status") or "").lower()
            }
            rows_to_insert.append(row)

        try:
            errors = self.client.insert_rows_json(self.table_ref, rows_to_insert)
            if errors == []:
                logger.info(f"🚀 Streamed {len(rows_to_insert)} rows to BigQuery successfully.")
                return True
            else:
                logger.error(f"⚠️ BigQuery Insert Errors: {errors}")
                return False
        except Exception as e:
            logger.error(f"❌ BigQuery Critical Error: {e}")
            return False
