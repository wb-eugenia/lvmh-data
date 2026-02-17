"""
Import products from HuggingFace dataset into SQL database.
Dataset: DBQ/Louis.Vuitton.Product.prices.France

Usage:
    python scripts/import_products_hf.py              # Full import
    python scripts/import_products_hf.py --dry-run     # Preview only
    python scripts/import_products_hf.py --batch 500   # Batch size
"""

import os
import sys
import argparse
import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.models_sql import Product

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./lvmh.db")
HF_DATASET = "DBQ/Louis.Vuitton.Product.prices.France"
DEFAULT_BATCH_SIZE = 500


def load_huggingface_dataset(dataset_name: str, sample_size: int = None) -> pd.DataFrame:
    """Load products from HuggingFace dataset."""
    logger.info(f"Loading dataset: {dataset_name}")
    
    try:
        from datasets import load_dataset
        ds = load_dataset(dataset_name, split="train")
        df = ds.to_pandas()
        logger.info(f"Loaded {len(df)} products from HuggingFace")
        
        if sample_size:
            df = df.head(sample_size)
            logger.info(f"Sampled {sample_size} products")
        
        return df
    except ImportError:
        logger.error("datasets library not installed. Run: pip install datasets")
        raise
    except Exception as e:
        logger.error(f"Failed to load dataset: {e}")
        raise


def import_products(df: pd.DataFrame, batch_size: int = DEFAULT_BATCH_SIZE, dry_run: bool = False):
    """Import products into SQL database."""
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    products_added = 0
    products_updated = 0
    products_skipped = 0
    
    try:
        for i, row in df.iterrows():
            sku = row.get('product_code') or row.get('sku') or row.get('item_id', '')
            if not sku:
                products_skipped += 1
                continue
            
            existing = session.query(Product).filter_by(sku=str(sku)).first()
            
            product_data = {
                'sku': str(sku),
                'name': row.get('title', '').strip() if pd.notna(row.get('title')) else '',
                'url': row.get('itemurl', '').strip() if pd.notna(row.get('itemurl')) else '',
                'image_url': row.get('imageurl', '').strip() if pd.notna(row.get('imageurl')) else '',
                'price_eur': float(row.get('price_eur', 0)) if pd.notna(row.get('price_eur')) else 0.0,
                'category1': str(row.get('category1_code', '')) if pd.notna(row.get('category1_code')) else '',
                'category2': str(row.get('category2_code', '')) if pd.notna(row.get('category2_code')) else '',
                'category3': str(row.get('category3_code', '')) if pd.notna(row.get('category3_code')) else '',
                'is_discount': bool(row.get('flg_discount', 0)) if pd.notna(row.get('flg_discount')) else False,
                'stock': 10,
            }
            
            if existing:
                if not dry_run:
                    for key, value in product_data.items():
                        setattr(existing, key, value)
                products_updated += 1
            else:
                if not dry_run:
                    product = Product(**product_data)
                    session.add(product)
                products_added += 1
            
            if (i + 1) % batch_size == 0:
                if not dry_run:
                    session.commit()
                logger.info(f"Processed {i + 1}/{len(df)} products...")
        
        if not dry_run:
            session.commit()
        
        total = session.query(Product).count()
        
        logger.info(f"Import complete!")
        logger.info(f"  Added: {products_added}")
        logger.info(f"  Updated: {products_updated}")
        logger.info(f"  Skipped: {products_skipped}")
        logger.info(f"  Total in database: {total}")
        
        return {'added': products_added, 'updated': products_updated, 'skipped': products_skipped, 'total': total}
        
    except Exception as e:
        logger.error(f"Error importing: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def export_products(output_file: str = 'products_export.csv'):
    """Export products from database to CSV."""
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        result = conn.execute("""
            SELECT sku, name, url, image_url, price_eur, 
                   category1, category2, category3, is_discount, stock 
            FROM products
        """)
        rows = result.fetchall()
    
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = __import__('csv').writer(f)
        writer.writerow(['sku', 'name', 'url', 'image_url', 'price_eur', 
                        'category1', 'category2', 'category3', 'is_discount', 'stock'])
        for row in rows:
            writer.writerow(row)
    
    logger.info(f"Exported {len(rows)} products to {output_file}")
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description='Import products from HuggingFace to SQL database')
    parser.add_argument('--dry-run', action='store_true', help='Preview without importing')
    parser.add_argument('--batch', type=int, default=DEFAULT_BATCH_SIZE, help='Batch size for commits')
    parser.add_argument('--sample', type=int, help='Limit number of products to import')
    parser.add_argument('--export', type=str, metavar='FILE', help='Export database to CSV')
    
    args = parser.parse_args()
    
    if args.export:
        count = export_products(args.export)
        print(f"Exported {count} products")
        return
    
    print(f"{'='*60}")
    print(f"🏪 LVMH PRODUCT IMPORT FROM HUGGINGFACE")
    print(f"{'='*60}")
    print(f"Dataset: {HF_DATASET}")
    if args.dry_run:
        print("MODE: DRY RUN (no changes will be made)")
    print(f"{'='*60}\n")
    
    df = load_huggingface_dataset(HF_DATASET, sample_size=args.sample)
    
    print(f"\nSample data (first 3 rows):")
    print(df.head(3).to_string())
    
    print(f"\nColumns: {list(df.columns)}")
    
    if args.dry_run:
        print(f"\n[DRY RUN] Would import {len(df)} products")
        return
    
    result = import_products(df, batch_size=args.batch)
    print(f"\n✅ Import complete!")


if __name__ == "__main__":
    main()
