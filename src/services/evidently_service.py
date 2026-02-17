"""
Evidently Service for LVMH Pipeline

Provides data drift detection and model monitoring for the extraction pipeline.
Uses statistical methods to detect drift in extraction outputs.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import statistics

logger = logging.getLogger(__name__)

EVIDENTLY_AVAILABLE = False
try:
    import evidently
    from evidently import Report
    from evidently.presets import DataDriftPreset
    EVIDENTLY_AVAILABLE = True
except ImportError as e:
    Report = None
    DataDriftPreset = None
    logger.warning(f"Evidently available for UI but using statistical drift detection: {e}")


@dataclass
class MonitoringResult:
    """Result of monitoring analysis."""
    drift_detected: bool
    drift_score: float
    num_drifted_columns: int
    total_columns: int
    column_drift: Dict[str, float]
    timestamp: str
    report_path: Optional[str] = None


@dataclass
class StatisticalDriftResult:
    """Statistical drift detection result."""
    feature: str
    reference_mean: float
    current_mean: float
    mean_change_pct: float
    reference_std: float
    current_std: float
    drift_detected: bool


class EvidentlyService:
    """
    Monitoring service for drift detection.
    
    Features:
    - Statistical drift detection in extraction outputs
    - Reference dataset management
    - HTML report generation
    - Integration with Evidently for visualization
    """
    
    def __init__(self, reports_dir: str = "data/reports"):
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self.reference_data: Optional[List[Dict[str, Any]]] = None
        self.reference_stats: Dict[str, Dict[str, float]] = {}
        self.evidently_available = EVIDENTLY_AVAILABLE
        
        logger.info(f"Evidently service initialized (Evidently UI: {self.evidently_available})")
    
    def set_reference_data(self, data: List[Dict[str, Any]]) -> bool:
        """
        Set reference dataset for drift comparison.
        
        Args:
            data: List of extracted notes to use as reference
            
        Returns:
            True if successful
        """
        try:
            features = self._extract_features(data)
            if not features:
                logger.warning("No features extracted from reference data")
                return False
            
            self.reference_data = features
            self.reference_stats = self._calculate_stats(features)
            logger.info(f"Reference data set with {len(features)} samples, {len(self.reference_stats)} features")
            return True
        except Exception as e:
            logger.error(f"Failed to set reference data: {e}")
            return False
    
    def _extract_features(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract numerical features from extracted notes."""
        features = []
        
        for item in data:
            record = {}
            
            if "extracted_data" in item:
                extracted = item["extracted_data"]
                if isinstance(extracted, str):
                    try:
                        extracted = json.loads(extracted)
                    except:
                        extracted = {}
                
                # Product pillar metrics
                record["num_products"] = len(extracted.get("produits", []))
                record["num_categories"] = len(extracted.get("categories", []))
                record["num_materials"] = len(extracted.get("materiaux", []))
                record["num_colors"] = len(extracted.get("couleurs", []))
                
                # Client pillar
                record["has_vip"] = 1 if extracted.get("profil_client", {}).get("is_vip") else 0
                record["has_budget"] = 1 if extracted.get("profil_client", {}).get("budget") else 0
                
                # Action pillar
                record["has_nba"] = 1 if extracted.get("action", {}).get("next_best_action") else 0
                record["urgency"] = extracted.get("action", {}).get("urgence", 0)
                
                # Quality metrics
                record["confidence"] = extracted.get("confidence", 0)
                record["num_extractions"] = sum([
                    len(extracted.get("produits", [])),
                    len(extracted.get("categories", [])),
                    len(extracted.get("materiaux", [])),
                    len(extracted.get("couleurs", [])),
                    len(extracted.get("profil_client", {}).get("contextes", [])),
                    len(extracted.get("profil_client", {}).get("preferences", [])),
                    len(extracted.get("hospitalite", {}).get("occasions", [])),
                    len(extracted.get("action", {}).get("recommandations", [])),
                ])
            
            # Metadata
            if "processing_time" in item:
                record["processing_time"] = item["processing_time"]
            if "tier" in item:
                record["tier"] = item["tier"]
            
            # Text length
            if "raw_text" in item:
                record["text_length"] = len(item.get("raw_text", ""))
            
            if record:
                features.append(record)
        
        return features
    
    def _calculate_stats(self, features: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
        """Calculate statistics for each feature."""
        if not features:
            return {}
        
        stats = {}
        for key in features[0].keys():
            values = [f[key] for f in features if key in f and f[key] is not None]
            if values:
                stats[key] = {
                    "mean": statistics.mean(values),
                    "std": statistics.stdev(values) if len(values) > 1 else 0,
                    "min": min(values),
                    "max": max(values),
                    "count": len(values)
                }
        return stats
    
    def check_drift(
        self,
        current_data: List[Dict[str, Any]],
        generate_report: bool = True,
        drift_threshold: float = 0.3
    ) -> Optional[MonitoringResult]:
        """
        Check for data drift against reference dataset.
        
        Args:
            current_data: Current batch of extracted notes
            generate_report: Whether to generate HTML report
            drift_threshold: Threshold for drift detection (default 30% change)
            
        Returns:
            MonitoringResult with drift analysis
        """
        if not self.reference_data:
            # Use current data as first reference
            logger.info("No reference data set, using current data as reference")
            self.set_reference_data(current_data)
            return MonitoringResult(
                drift_detected=False,
                drift_score=0.0,
                num_drifted_columns=0,
                total_columns=0,
                column_drift={},
                timestamp=datetime.utcnow().isoformat()
            )
        
        try:
            current_features = self._extract_features(current_data)
            
            if not current_features or not self.reference_stats:
                logger.warning("Insufficient data for drift detection")
                return None
            
            current_stats = self._calculate_stats(current_features)
            
            # Calculate drift for each feature
            drift_results = []
            column_drift = {}
            
            for feature, ref_stats in self.reference_stats.items():
                if feature not in current_stats:
                    continue
                
                curr_stats = current_stats[feature]
                
                # Calculate mean change percentage
                if ref_stats["mean"] != 0:
                    mean_change = abs(curr_stats["mean"] - ref_stats["mean"]) / abs(ref_stats["mean"])
                else:
                    mean_change = 1.0 if curr_stats["mean"] != 0 else 0.0
                
                drift_detected = mean_change > drift_threshold
                
                drift_results.append(StatisticalDriftResult(
                    feature=feature,
                    reference_mean=ref_stats["mean"],
                    current_mean=curr_stats["mean"],
                    mean_change_pct=mean_change,
                    reference_std=ref_stats["std"],
                    current_std=curr_stats["std"],
                    drift_detected=drift_detected
                ))
                
                if drift_detected:
                    column_drift[feature] = mean_change
            
            # Calculate overall drift score
            total_features = len(drift_results)
            drifted_features = sum(1 for r in drift_results if r.drift_detected)
            drift_score = drifted_features / total_features if total_features > 0 else 0.0
            drift_detected = drift_score > 0.2  # More than 20% features drifted
            
            # Generate HTML report if requested
            report_path = None
            if generate_report:
                report_path = self._generate_html_report(drift_results, f"drift_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}")
            
            return MonitoringResult(
                drift_detected=drift_detected,
                drift_score=drift_score,
                num_drifted_columns=drifted_features,
                total_columns=total_features,
                column_drift=column_drift,
                timestamp=datetime.utcnow().isoformat(),
                report_path=report_path
            )
            
        except Exception as e:
            logger.error(f"Drift check failed: {e}")
            return None
    
    def _generate_html_report(self, drift_results: List[StatisticalDriftResult], name: str) -> str:
        """Generate HTML report from drift results."""
        try:
            report_path = self.reports_dir / f"{name}.html"
            
            # Filter to only drifted columns for the report
            drifted = [r for r in drift_results if r.drift_detected]
            not_drifted = [r for r in drift_results if not r.drift_detected]
            
            # Calculate overall stats
            total = len(drift_results)
            drift_pct = (len(drifted) / total * 100) if total > 0 else 0
            
            html = f"""<!DOCTYPE html>
<html>
<head>
    <title>LVMH Pipeline - Drift Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
               max-width: 900px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); 
                  color: white; padding: 30px; border-radius: 10px; margin-bottom: 20px; }}
        .card {{ background: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .status {{ display: inline-block; padding: 8px 16px; border-radius: 20px; font-weight: bold; }}
        .status.ok {{ background: #d4edda; color: #155724; }}
        .status.alert {{ background: #f8d7da; color: #721c24; }}
        .metric {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #eee; }}
        .metric:last-child {{ border-bottom: none; }}
        .metric-label {{ color: #666; }}
        .metric-value {{ font-weight: bold; }}
        .drift-badge {{ background: #dc3545; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; }}
        .no-drift-badge {{ background: #28a745; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f9fa; font-weight: 600; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>LVMH Pipeline Monitoring</h1>
        <p>Drift Detection Report - {name}</p>
        <p>Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
    </div>
    
    <div class="card">
        <h2>Drift Status</h2>
        <p><span class="status {'ok' if drift_pct < 20 else 'alert'}">
            {'NO SIGNIFICANT DRIFT' if drift_pct < 20 else 'DRIFT DETECTED'}
        </span></p>
        <div class="metric">
            <span class="metric-label">Overall Drift Score</span>
            <span class="metric-value">{drift_pct:.1f}%</span>
        </div>
        <div class="metric">
            <span class="metric-label">Features Analyzed</span>
            <span class="metric-value">{total}</span>
        </div>
        <div class="metric">
            <span class="metric-label">Drifted Features</span>
            <span class="metric-value">{len(drifted)}</span>
        </div>
    </div>
    
    <div class="card">
        <h2>Drifted Features ({len(drifted)})</h2>
"""
            
            if drifted:
                html += """        <table>
            <tr><th>Feature</th><th>Reference Mean</th><th>Current Mean</th><th>Change</th></tr>
"""
                for r in drifted:
                    html += f"""            <tr>
                <td>{r.feature}</td>
                <td>{r.reference_mean:.2f}</td>
                <td>{r.current_mean:.2f}</td>
                <td><span class="drift-badge">+{r.mean_change_pct:.1%}</span></td>
            </tr>
"""
                html += "        </table>"
            else:
                html += "<p>No drifted features detected.</p>"
            
            html += """
    </div>
    
    <div class="card">
        <h2>All Features</h2>
        <table>
            <tr><th>Feature</th><th>Reference Mean</th><th>Current Mean</th><th>Change</th><th>Status</th></tr>
"""
            
            for r in drift_results:
                badge_class = "drift-badge" if r.drift_detected else "no-drift-badge"
                badge_text = "DRIFT" if r.drift_detected else "OK"
                html += f"""            <tr>
                <td>{r.feature}</td>
                <td>{r.reference_mean:.2f}</td>
                <td>{r.current_mean:.2f}</td>
                <td>{r.mean_change_pct:.1%}</td>
                <td><span class="{badge_class}">{badge_text}</span></td>
            </tr>
"""
            
            html += """
        </table>
    </div>
    
    <div class="card">
        <h2>Recommendations</h2>
        <ul>
            <li>If drift is detected, review recent changes to the pipeline</li>
            <li>Check taxonomy updates that may affect extraction</li>
            <li>Consider updating the reference dataset with recent data</li>
            <li>Monitor for data quality issues in source systems</li>
        </ul>
    </div>
</body>
</html>"""
            
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(html)
            
            logger.info(f"Report saved to {report_path}")
            return str(report_path)
            
        except Exception as e:
            logger.error(f"Failed to generate HTML report: {e}")
            return None
    
    def get_reports_list(self) -> List[Dict[str, str]]:
        """Get list of available reports."""
        reports = []
        for f in self.reports_dir.glob("*.html"):
            reports.append({
                "name": f.stem,
                "path": str(f),
                "created": datetime.fromtimestamp(f.stat().st_ctime).isoformat()
            })
        return sorted(reports, key=lambda x: x["created"], reverse=True)
    
    def get_reference_stats(self) -> Dict[str, Dict[str, float]]:
        """Get reference dataset statistics."""
        return self.reference_stats


# Singleton instance
_service: Optional[EvidentlyService] = None


def get_evidently_service() -> EvidentlyService:
    """Get singleton instance of EvidentlyService."""
    global _service
    if _service is None:
        _service = EvidentlyService()
    return _service


def check_drift(current_data: List[Dict[str, Any]], generate_report: bool = False) -> Optional[MonitoringResult]:
    """
    Convenience function to check for data drift.
    
    Args:
        current_data: Current batch of extracted notes
        generate_report: Whether to generate HTML report
        
    Returns:
        MonitoringResult with drift analysis
    """
    service = get_evidently_service()
    return service.check_drift(current_data, generate_report=generate_report)
