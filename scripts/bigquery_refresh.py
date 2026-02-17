"""
BigQuery Scheduled Queries
Automatically refresh aggregated tables.
"""

from google.cloud import bigquery
import os

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "elite-hold-485510-t5")
DATASET = "lvmh_data"

client = bigquery.Client(project=PROJECT_ID)

# Scheduled query to refresh daily_metrics every hour
REFRESH_DAILY_METRICS = f"""
CREATE OR REPLACE TABLE `{PROJECT_ID}.{DATASET}.daily_metrics`
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
FROM `{PROJECT_ID}.{DATASET}.notes`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY 1, 2
"""

# Scheduled query to refresh advisor_metrics every hour
REFRESH_ADVISOR_METRICS = f"""
CREATE OR REPLACE TABLE `{PROJECT_ID}.{DATASET}.advisor_metrics`
PARTITION BY date
AS SELECT
  DATE(timestamp) as date,
  advisor_id,
  store_id,
  COUNT(*) as notes_count,
  SUM(points_awarded) as total_points,
  AVG(quality_score) as avg_quality_score,
  COUNTIF(is_vic = true) as vic_served
FROM `{PROJECT_ID}.{DATASET}.notes`
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)
GROUP BY 1, 2, 3
"""

def refresh_tables():
    """Refresh all aggregated tables."""
    print("Refreshing daily_metrics...")
    client.query(REFRESH_DAILY_METRICS).result()
    print("[OK] daily_metrics refreshed")
    
    print("Refreshing advisor_metrics...")
    client.query(REFRESH_ADVISOR_METRICS).result()
    print("[OK] advisor_metrics refreshed")
    
    print("All tables refreshed!")

if __name__ == "__main__":
    refresh_tables()
