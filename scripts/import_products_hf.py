"""
Export products to CSV from local database.
"""

import os
import sys
import csv
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./lvmh.db")

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    result = conn.execute(text("SELECT sku, name, url, image_url, price_eur, category1, category2, category3, is_discount, stock FROM products"))
    rows = result.fetchall()

with open('products_export.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['sku', 'name', 'url', 'image_url', 'price_eur', 'category1', 'category2', 'category3', 'is_discount', 'stock'])
    for row in rows:
        writer.writerow(row)

print(f"Exported {len(rows)} products to products_export.csv")
    
    products_added = 0
    products_updated = 0
    
    try:
        for i, row in enumerate(ds):
            sku = row.get('product_code', '')
            if not sku:
                continue
            
            existing = session.query(Product).filter_by(sku=sku).first()
            
            product_data = {
                'sku': sku,
                'name': row.get('title', ''),
                'url': row.get('itemurl', ''),
                'image_url': row.get('imageurl', ''),
                'price_eur': row.get('price_eur', 0) or 0,
                'category1': row.get('category1_code', ''),
                'category2': row.get('category2_code', ''),
                'category3': row.get('category3_code', ''),
                'is_discount': bool(row.get('flg_discount', 0)),
                'stock': 10,
            }
            
            if existing:
                for key, value in product_data.items():
                    setattr(existing, key, value)
                products_updated += 1
            else:
                product = Product(**product_data)
                session.add(product)
                products_added += 1
            
            if (i + 1) % batch_size == 0:
                session.commit()
                logger.info(f"Processed {i + 1}/{len(ds)} products...")
        
        session.commit()
        logger.info(f"Import complete! Added: {products_added}, Updated: {products_updated}")
        
        total = session.query(Product).count()
        logger.info(f"Total products in database: {total}")
        
    except Exception as e:
        logger.error(f"Error importing: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    import_products()
