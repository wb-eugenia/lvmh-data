import pandas as pd
import os
import json
import ast
from tqdm import tqdm
from pathlib import Path
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.extractor import TagExtractor

def migrate_dataset(
    input_path='outputs/wave1_tagged_dataset.xlsx',
    output_path='outputs/wave1_migrated_v2.xlsx'
):
    """
    Migrate dataset from v1 to v2 taxonomy.
    """
    if not os.path.exists(input_path):
        print(f"❌ Input file not found: {input_path}")
        return

    print(f"🚀 Starting migration v1 -> v2 on {input_path}")
    
    # Load dataset
    try:
        df = pd.read_excel(input_path)
        print(f"📊 Loaded {len(df)} notes")
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return

    # Initialize extractor with v2 taxonomy
    try:
        extractor = TagExtractor(
            taxonomy_path="config/taxonomy_v1.json",
            model="gpt-4o-mini",
            cache_dir="cache_v2"  # Separate cache for v2
        )
        print("✅ Extractor v2 initialized")
    except Exception as e:
        print(f"❌ Error initializing extractor: {e}")
        return

    # Migration stats
    stats = {
        'processed': 0,
        'tags_v1_count': 0,
        'tags_v2_count': 0,
        'new_metadata_count': 0
    }

    results = []
    
    # Process each note
    for idx, row in tqdm(df.iterrows(), total=len(df)):
        client_id = row.get('ID') or row.get('client_id')
        transcription = row.get('Transcription')
        language = row.get('Language', 'EN')
        
        # Count v1 tags
        v1_tags = []
        if 'tags_extracted' in row:
            val = row['tags_extracted']
            if isinstance(val, str):
                try:
                    if val.startswith('['):
                        v1_tags = ast.literal_eval(val)
                    else:
                        v1_tags = val.split(',')
                except: pass
            elif isinstance(val, list):
                v1_tags = val
        
        stats['tags_v1_count'] += len(v1_tags)

        # Re-extract with v2
        try:
            result = extractor.extract(
                transcription=transcription,
                language=language,
                client_id=client_id,
                use_cache=True
            )
            
            # Update stats
            stats['tags_v2_count'] += len(result['tags'])
            if result.get('allergy_severity') or result.get('relationship_context'):
                stats['new_metadata_count'] += 1
            
            # Merge result into row
            new_row = row.to_dict()
            new_row['tags_v2'] = result['tags']
            new_row['tags_extracted'] = result['tags'] # Update main column
            new_row['confidence_v2'] = result['confidence']
            new_row['allergy_severity'] = str(result.get('allergy_severity', {}))
            new_row['relationship_context'] = str(result.get('relationship_context', {}))
            new_row['profession_v2'] = result.get('profession')
            
            results.append(new_row)
            stats['processed'] += 1
            
        except Exception as e:
            print(f"⚠️ Error processing {client_id}: {e}")
            results.append(row.to_dict()) # Keep original if fail

    # Create new DataFrame
    new_df = pd.DataFrame(results)
    
    # Save
    new_df.to_excel(output_path, index=False)
    print(f"✅ Migration complete! Saved to {output_path}")
    
    # Report
    print("\n=== MIGRATION REPORT ===")
    print(f"Notes processed: {stats['processed']}")
    print(f"Total Tags v1: {stats['tags_v1_count']} (Avg: {stats['tags_v1_count']/len(df):.1f})")
    print(f"Total Tags v2: {stats['tags_v2_count']} (Avg: {stats['tags_v2_count']/len(df):.1f})")
    
    if stats['tags_v1_count'] > 0:
        gain = stats['tags_v2_count'] - stats['tags_v1_count']
        pct = (stats['tags_v2_count']/stats['tags_v1_count'] - 1)*100
        print(f"Gain: +{gain} tags (+{pct:.1f}%)")
    else:
        print(f"Gain: +{stats['tags_v2_count']} tags (Baseline was 0 or unreadable)")
        
    print(f"Notes with new metadata: {stats['new_metadata_count']}")

if __name__ == "__main__":
    migrate_dataset()
