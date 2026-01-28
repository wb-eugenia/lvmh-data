"""
Pipeline v2: Multi-Tier Orchestrator.
Routes notes through Tier 1/2/3 based on complexity.
- Tier 1: Rules (regex) - FREE
- Tier 2: Ollama Qwen 2.5 7B - FREE (local)
- Tier 3: GPT-4o-mini - $0.0001/note
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import pandas as pd
from tqdm import tqdm

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.smart_router import SmartRouter
from src.tier1_rules import Tier1RulesEngine
from src.tier2_nlp import Tier2OllamaEngine
from src.rgpd_ollama import RGPDOllamaFilter
from src.extractor import TagExtractor
from src.cache_manager import CacheManager
from src.cost_tracker import CostTracker


class PipelineV2:
    """
    Multi-tier processing pipeline.
    
    Tier 1: Rules-based (0€, ~0.01s/note)
    Tier 2: Ollama Qwen 2.5 7B (0€, ~3s/note)
    Tier 3: GPT-4o-mini ($0.0001/note, ~3s/note)
    """
    
    def __init__(self, use_cache: bool = True):
        self.router = SmartRouter()
        self.tier1 = Tier1RulesEngine()
        self.tier2 = None  # Lazy load
        self.tier3 = None  # Lazy load
        self.rgpd_filter = None # Lazy load
        self.cache = CacheManager('cache/pipeline_v2') if use_cache else None
        self.cost_tracker = CostTracker()
        self.use_cache = use_cache
        self.results = []
        self.tier2_available = True
    
    def _init_tier2(self):
        """Lazy load Tier 2 Ollama engine."""
        if self.tier2 is None:
            try:
                self.tier2 = Tier2OllamaEngine()
                self.tier2_available = True
            except Exception as e:
                print(f"⚠️ Tier 2 Ollama not available: {e}")
                self.tier2_available = False
    
    def _init_rgpd(self):
        """Lazy load RGPD Ollama filter."""
        if self.rgpd_filter is None:
            try:
                self.rgpd_filter = RGPDOllamaFilter()
            except:
                self.rgpd_filter = None

    def _init_tier3(self):
        """Lazy load Tier 3 LLM extractor."""
        if self.tier3 is None:
            self.tier3 = TagExtractor()
    
    def process_single(self, note: Dict) -> Dict:
        """Process a single note through appropriate tier."""
        text = note.get('Transcription', '')
        language = note.get('Language', 'FR')
        note_id = note.get('ID', 'unknown')
        
        # Route to tier
        decision = self.router.route(text, language, note)
        tier = decision.tier
        
        # Check cache first
        if self.cache:
            cache_key = self.cache.get_cache_key(text, f'tier{tier}')
            cached = self.cache.load(cache_key, f'tier{tier}')
            if cached:
                cached['from_cache'] = True
                cached['tier'] = tier
                return cached
        
        # RGPD Check (Local) - Run for all notes to be safe
        self._init_rgpd()
        rgpd_result = None
        if self.rgpd_filter:
            rgpd_result = self.rgpd_filter.detect(text, language)
            if rgpd_result.contains_sensitive:
                # If sensitive, force Tier 3 for secure handling/anonymization
                if tier < 3:
                    tier = 3
                    decision.reasons.insert(0, f"RGPD Sensitive: {rgpd_result.categories_detected}")
        
        # Process based on tier
        if tier == 1:
            result = self._process_tier1(text, language)
        elif tier == 2:
            result = self._process_tier2(text, language)
            
            # === SAFETY FALLBACK ===
            # If Tier 2 detects high severity or critical issues, escalate to Tier 3
            needs_escalation = False
            escalation_reason = ""
            
            # Check allergy severity
            if result.get('allergy_severity') == 'high':
                needs_escalation = True
                escalation_reason = "Tier 2 detected HIGH severity allergy"
            
            # Check critical VIP (if Tier 2 flagged it as 'vic' or 'ultimate')
            if result.get('client_status') in ['vic', 'ultimate', 'platinum']:
                # Optional: keep VIP in Tier 2 if confidence is high, but escalate for safety
                if result.get('confidence', 0) < 0.9:
                    needs_escalation = True
                    escalation_reason = "Tier 2 detected VIC/Ultimate with low confidence"
            
            if needs_escalation:
                print(f"⚠️ ESCALATING Note {note_id} to Tier 3: {escalation_reason}")
                tier = 3
                decision.reasons.append(f"Escalated: {escalation_reason}")
                result = self._process_tier3(text, language, note_id)
                
        else:
            result = self._process_tier3(text, language, note_id)
        
        # Add metadata
        result['ID'] = note_id
        result['tier'] = tier
        result['routing_reasons'] = decision.reasons
        result['routing_confidence'] = decision.confidence
        result['from_cache'] = False
        
        # Add RGPD info if available
        if rgpd_result:
            result['rgpd_sensitive'] = rgpd_result.contains_sensitive
            result['rgpd_categories'] = rgpd_result.categories_detected
        
        # Cache result
        if self.cache:
            self.cache.save(cache_key, f'tier{tier}', result)
        
        return result
    
    def _process_tier1(self, text: str, language: str) -> Dict:
        """Process with Tier 1 rules engine."""
        extraction = self.tier1.extract(text, language)
        return {
            'tags': extraction.tags,
            'confidence': extraction.confidence,
            'budget_range': extraction.budget_range,
            'client_status': extraction.client_status,
            'profession': extraction.profession,
            'age': extraction.age,
            'gender': extraction.gender,
            'relationship_context': extraction.relationship_context,
            'extracted_by': 'tier1_rules',
            'cost': 0.0
        }
    
    def _process_tier2(self, text: str, language: str) -> Dict:
        """Process with Tier 2 Ollama engine."""
        self._init_tier2()
        
        if not self.tier2_available or self.tier2 is None:
            # Fallback to Tier 1 if Ollama not available
            return self._process_tier1(text, language)
        
        extraction = self.tier2.extract(text, language)
        return {
            'tags': extraction.tags,
            'confidence': extraction.confidence,
            'budget_range': extraction.budget_range,
            'client_status': extraction.client_status,
            'profession': extraction.profession,
            'allergies': extraction.allergies,
            'dietary': extraction.dietary,
            'relationship_context': extraction.relationship_context,
            'reasoning': extraction.reasoning,
            'extracted_by': 'tier2_ollama',
            'cost': 0.0
        }
    
    def _process_tier3(self, text: str, language: str, client_id: str) -> Dict:
        """Process with Tier 3 LLM."""
        self._init_tier3()
        extraction = self.tier3.extract(
            transcription=text,
            language=language,
            client_id=client_id,
            use_cache=False  # We handle caching at pipeline level
        )
        
        # Track cost
        cost = 0.0001  # Approximate cost per note
        
        return {
            'tags': extraction.get('tags', []),
            'confidence': extraction.get('confidence', 0.5),
            'budget_range': extraction.get('budget_range'),
            'client_status': extraction.get('client_status'),
            'profession': extraction.get('profession'),
            'allergies': extraction.get('allergies', []),
            'allergy_severity': extraction.get('allergy_severity', {}),
            'relationship_context': extraction.get('relationship_context', {}),
            'reasoning': extraction.get('reasoning'),
            'extracted_by': 'tier3_llm',
            'cost': cost
        }
    
    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """Run pipeline on dataframe."""
        start_time = datetime.now()
        
        print(f"🚀 PIPELINE V2 MULTI-TIER - {start_time.strftime('%H:%M:%S')}")
        print("="*60)
        print("Tiers: Rules (0€) → Ollama Qwen 2.5 7B (0€) → GPT-4o-mini ($)")
        print("="*60)
        
        self.results = []
        total_cost = 0.0
        tier_counts = {1: 0, 2: 0, 3: 0}
        
        for _, row in tqdm(df.iterrows(), total=len(df), desc="Processing"):
            note = row.to_dict()
            result = self.process_single(note)
            
            # Merge with original data
            combined = {
                'ID': note.get('ID'),
                'Date': note.get('Date'),
                'Duration': note.get('Duration'),
                'Language': note.get('Language'),
                'Transcription': note.get('Transcription', '')[:200] + '...',
                **result
            }
            
            self.results.append(combined)
            tier_counts[result['tier']] += 1
            total_cost += result.get('cost', 0)
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Summary stats
        total_notes = len(df)
        tier1_pct = tier_counts[1] / total_notes * 100
        tier2_pct = tier_counts[2] / total_notes * 100
        tier3_pct = tier_counts[3] / total_notes * 100
        savings = (tier_counts[1] + tier_counts[2]) / total_notes * 100
        
        # Generate report
        print("\n" + "="*60)
        print("📊 PIPELINE V2 COMPLETE")
        print("="*60)
        print(f"Notes processed: {total_notes}")
        print(f"Duration: {duration:.1f}s ({duration/total_notes:.2f}s/note)")
        
        print(f"\n🔀 TIER DISTRIBUTION:")
        print(f"  Tier 1 (Rules):  {tier_counts[1]:>4} ({tier1_pct:>5.1f}%) - 0€")
        print(f"  Tier 2 (Ollama): {tier_counts[2]:>4} ({tier2_pct:>5.1f}%) - 0€")
        print(f"  Tier 3 (GPT):    {tier_counts[3]:>4} ({tier3_pct:>5.1f}%) - ${tier_counts[3] * 0.0001:.4f}")
        
        print(f"\n💰 COST SAVINGS:")
        print(f"  Total API cost: ${total_cost:.4f}")
        print(f"  All-LLM cost:   ${total_notes * 0.0001:.4f}")
        print(f"  Savings:        ${(total_notes * 0.0001 - total_cost):.4f} ({savings:.0f}%)")
        
        if self.cache:
            print(self.cache.report())
        
        return pd.DataFrame(self.results)
    
    def export(self, output_dir: str = 'outputs'):
        """Export results."""
        Path(output_dir).mkdir(exist_ok=True)
        
        df = pd.DataFrame(self.results)
        
        # Convert complex types for Excel
        df_export = df.copy()
        for col in df_export.columns:
            if df_export[col].apply(lambda x: isinstance(x, (list, dict))).any():
                df_export[col] = df_export[col].apply(
                    lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, (list, dict)) else x
                )
        
        # Export formats
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        base = f'{output_dir}/pipeline_v2_{timestamp}'
        df_export.to_excel(f'{base}.xlsx', index=False)
        df_export.to_csv(f'{base}.csv', index=False)
        df.to_json(f'{base}.json', orient='records', indent=2, force_ascii=False)
        
        # Also save latest
        df_export.to_excel(f'{output_dir}/pipeline_v2_latest.xlsx', index=False)
        
        print(f"\n✅ Exported to {base}.[xlsx|csv|json]")
        
        return df


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Run Pipeline V2 Multi-Tier')
    parser.add_argument('-n', '--notes', type=int, default=None,
                       help='Number of notes to process (default: all)')
    parser.add_argument('--no-cache', action='store_true',
                       help='Disable caching')
    args = parser.parse_args()
    
    # Load Wave 2 cleaned data
    df = pd.read_csv('data/processed/LVMH_Notes_CA101-400_cleaned.csv')
    
    if args.notes:
        df = df.head(args.notes)
    
    pipeline = PipelineV2(use_cache=not args.no_cache)
    results = pipeline.run(df)
    pipeline.export()
