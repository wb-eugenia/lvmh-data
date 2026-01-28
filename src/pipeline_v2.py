"""
Pipeline v2: Multi-Tier Orchestrator.
Routes notes through Tier 1/2/3 based on complexity.
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
from src.tier2_nlp import Tier2NLPEngine
from src.extractor import TagExtractor
from src.cache_manager import CacheManager
from src.cost_tracker import CostTracker


class PipelineV2:
    """
    Multi-tier processing pipeline.
    
    Tier 1: Rules-based (0€, 0.5s/note)
    Tier 2: Local NLP (0€, 1.5s/note)
    Tier 3: LLM Premium ($0.0001/note, 3s/note)
    """
    
    def __init__(self, use_cache: bool = True):
        self.router = SmartRouter()
        self.tier1 = Tier1RulesEngine()
        self.tier2 = None  # Lazy load (heavy)
        self.tier3 = None  # Lazy load (needs API key)
        self.cache = CacheManager('cache/pipeline_v2') if use_cache else None
        self.cost_tracker = CostTracker()
        self.use_cache = use_cache
        self.results = []
    
    def _init_tier2(self):
        """Lazy load Tier 2 NLP engine."""
        if self.tier2 is None:
            self.tier2 = Tier2NLPEngine()
            self.tier2.load_embeddings()
    
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
        
        # Process based on tier
        if tier == 1:
            result = self._process_tier1(text, language)
        elif tier == 2:
            result = self._process_tier2(text, language)
        else:
            result = self._process_tier3(text, language, note_id)
        
        # Add metadata
        result['ID'] = note_id
        result['tier'] = tier
        result['routing_reasons'] = decision.reasons
        result['routing_confidence'] = decision.confidence
        result['from_cache'] = False
        
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
            'extracted_by': 'tier1_rules',
            'cost': 0.0
        }
    
    def _process_tier2(self, text: str, language: str) -> Dict:
        """Process with Tier 2 NLP engine."""
        self._init_tier2()
        extraction = self.tier2.extract(text, language)
        return {
            'tags': extraction.tags,
            'tag_scores': extraction.tag_scores,
            'confidence': extraction.confidence,
            'budget_range': extraction.budget_range,
            'keywords': extraction.keywords,
            'extracted_by': 'tier2_nlp',
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
        
        print(f"🚀 PIPELINE V2 STARTED - {start_time.strftime('%H:%M:%S')}")
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
        
        # Generate report
        print("\n" + "="*60)
        print("📊 PIPELINE V2 COMPLETE")
        print("="*60)
        print(f"Notes processed: {len(df)}")
        print(f"Duration: {duration:.1f}s ({duration/len(df):.2f}s/note)")
        print(f"\n🔀 TIER DISTRIBUTION:")
        print(f"  Tier 1 (Rules): {tier_counts[1]} ({tier_counts[1]/len(df)*100:.1f}%)")
        print(f"  Tier 2 (NLP):   {tier_counts[2]} ({tier_counts[2]/len(df)*100:.1f}%)")
        print(f"  Tier 3 (LLM):   {tier_counts[3]} ({tier_counts[3]/len(df)*100:.1f}%)")
        print(f"\n💰 COST:")
        print(f"  Total: ${total_cost:.4f}")
        print(f"  Savings vs all-LLM: ${(len(df) * 0.0001 - total_cost):.4f} ({(1 - total_cost/(len(df)*0.0001))*100:.0f}%)")
        
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
        base = f'{output_dir}/pipeline_v2_results'
        df_export.to_excel(f'{base}.xlsx', index=False)
        df_export.to_csv(f'{base}.csv', index=False)
        df.to_json(f'{base}.json', orient='records', indent=2, force_ascii=False)
        
        print(f"\n✅ Exported to {base}.[xlsx|csv|json]")
        
        return df


if __name__ == "__main__":
    # Test on Wave 2 data
    df = pd.read_csv('data/processed/LVMH_Notes_CA101-400_cleaned.csv')
    
    pipeline = PipelineV2(use_cache=True)
    results = pipeline.run(df.head(20))  # Test on 20 first
    pipeline.export()
