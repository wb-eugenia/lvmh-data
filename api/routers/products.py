"""
Products router - Browse product catalog with images and stock.
Uses SQL database for products with RAG index support.
"""

import os
import sys
import logging
import pickle
import json
import io
import csv
from typing import Optional, List
from pathlib import Path

from fastapi import APIRouter, Query, HTTPException, UploadFile, File, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from api.database import get_db
from api.models_sql import Product as ProductModel

logger = logging.getLogger("lvmh-api.products")
router = APIRouter()

INDEX_PATH = Path(__file__).parent.parent.parent / "data" / "vector_store" / "lv_index.pkl"

_cache = None
_rag_index_needs_rebuild = False


def _get_db_products(db: Session, skip: int = 0, limit: int = 100):
    """Get products from SQL database."""
    return db.query(ProductModel).offset(skip).limit(limit).all()


def _count_db_products(db: Session) -> int:
    """Count products in database."""
    return db.query(func.count(ProductModel.id)).scalar()


class ProductResponse(BaseModel):
    sku: str
    name: str
    url: Optional[str] = None
    image_url: Optional[str] = None
    price_eur: float
    category1: Optional[str] = None
    category2: Optional[str] = None
    category3: Optional[str] = None
    is_discount: bool = False
    stock: int = 10
    rag_indexed: bool = False


class ProductCreate(BaseModel):
    sku: str
    name: str
    url: Optional[str] = None
    image_url: Optional[str] = None
    price_eur: float = 0.0
    category1: Optional[str] = None
    category2: Optional[str] = None
    category3: Optional[str] = None
    is_discount: bool = False
    stock: int = 10


@router.get("/products", response_model=dict)
async def get_products(
    category: Optional[str] = Query(None, description="Filter by category"),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    search: Optional[str] = Query(None, description="Search in product name"),
    in_stock_only: bool = Query(False, description="Show only products in stock"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get products with pagination and filters from SQL database.
    """
    query = db.query(ProductModel)
    
    if category:
        query = query.filter(ProductModel.category1.ilike(f"%{category}%"))
    
    if min_price is not None:
        query = query.filter(ProductModel.price_eur >= min_price)
    
    if max_price is not None:
        query = query.filter(ProductModel.price_eur <= max_price)
    
    if search:
        query = query.filter(ProductModel.name.ilike(f"%{search}%"))
    
    if in_stock_only:
        query = query.filter(ProductModel.stock > 0)
    
    total = query.count()
    
    start = (page - 1) * limit
    products_db = query.offset(start).limit(limit).all()
    
    products = []
    for p in products_db:
        products.append({
            "sku": p.sku,
            "name": p.name,
            "url": p.url,
            "image_url": p.image_url,
            "price_eur": p.price_eur,
            "category1": p.category1,
            "category2": p.category2,
            "category3": p.category3,
            "is_discount": p.is_discount,
            "stock": p.stock,
            "rag_indexed": p.rag_indexed,
        })
    
    return {
        "products": products,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit if total > 0 else 0
    }


@router.get("/products/categories", response_model=dict)
async def get_categories(db: Session = Depends(get_db)):
    """Get all available product categories."""
    categories = db.query(
        ProductModel.category1, 
        func.count(ProductModel.id).label('count')
    ).filter(
        ProductModel.category1.isnot(None)
    ).group_by(ProductModel.category1).all()
    
    cat_dict = {c[0]: c[1] for c in categories if c[0]}
    return {"categories": cat_dict}


@router.get("/products/stats", response_model=dict)
async def get_product_stats(db: Session = Depends(get_db)):
    """Get product catalog statistics."""
    total = _count_db_products(db)
    
    if total == 0:
        return {
            "total": 0,
            "categories": {},
            "avg_price_eur": 0,
            "min_price_eur": 0,
            "max_price_eur": 0,
            "discount_count": 0,
            "in_stock_count": 0,
            "indexed_count": 0,
        }
    
    stats = db.query(
        func.avg(ProductModel.price_eur).label('avg_price'),
        func.min(ProductModel.price_eur).label('min_price'),
        func.max(ProductModel.price_eur).label('max_price'),
        func.sum(func.cast(ProductModel.is_discount, int)).label('discount_count'),
        func.sum(func.cast(ProductModel.stock > 0, int)).label('in_stock_count'),
        func.sum(func.cast(ProductModel.rag_indexed, int)).label('indexed_count'),
    ).first()
    
    return {
        "total": total,
        "categories": {},
        "avg_price_eur": round(stats.avg_price or 0, 2),
        "min_price_eur": stats.min_price or 0,
        "max_price_eur": stats.max_price or 0,
        "discount_count": stats.discount_count or 0,
        "in_stock_count": stats.in_stock_count or 0,
        "indexed_count": stats.indexed_count or 0,
    }


@router.post("/products", response_model=dict)
async def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    """Create a new product."""
    existing = db.query(ProductModel).filter(ProductModel.sku == product.sku).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Product with SKU {product.sku} already exists")
    
    db_product = ProductModel(
        sku=product.sku,
        name=product.name,
        url=product.url,
        image_url=product.image_url,
        price_eur=product.price_eur,
        category1=product.category1,
        category2=product.category2,
        category3=product.category3,
        is_discount=product.is_discount,
        stock=product.stock,
        rag_indexed=False,
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    
    global _rag_index_needs_rebuild
    _rag_index_needs_rebuild = True
    
    return {"sku": db_product.sku, "created": True}


@router.put("/products/{sku}/stock", response_model=dict)
async def update_product_stock(sku: str, stock: int = Query(..., ge=0), db: Session = Depends(get_db)):
    """Update stock for a specific product."""
    if stock < 0:
        raise HTTPException(status_code=400, detail="Stock cannot be negative")
    
    product = db.query(ProductModel).filter(ProductModel.sku == sku).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {sku} not found")
    
    product.stock = stock
    db.commit()
    
    return {"sku": sku, "stock": stock, "updated": True}


@router.delete("/products/{sku}", response_model=dict)
async def delete_product(sku: str, db: Session = Depends(get_db)):
    """Delete a product."""
    product = db.query(ProductModel).filter(ProductModel.sku == sku).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {sku} not found")
    
    db.delete(product)
    db.commit()
    
    global _rag_index_needs_rebuild
    _rag_index_needs_rebuild = True
    
    return {"sku": sku, "deleted": True}


@router.post("/products/import-csv", response_model=dict)
async def import_products_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Import products from CSV file."""
    content = await file.read()
    
    try:
        decoded = content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(decoded))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV file: {str(e)}")
    
    imported = 0
    updated = 0
    errors = []
    
    for row_num, row in enumerate(reader, start=2):
        try:
            sku = row.get('sku', row.get('product_code', '')).strip()
            if not sku:
                errors.append(f"Row {row_num}: Missing SKU")
                continue
            
            name = row.get('title', row.get('name', '')).strip()
            if not name:
                errors.append(f"Row {row_num}: Missing name for SKU {sku}")
                continue
            
            price_eur = 0.0
            try:
                price_eur = float(row.get('price_eur', row.get('price', 0)))
            except:
                pass
            
            stock = 10
            try:
                stock = int(row.get('stock', 10))
            except:
                pass
            
            existing = db.query(ProductModel).filter(ProductModel.sku == sku).first()
            
            if existing:
                existing.name = name
                existing.url = row.get('itemurl', row.get('url', ''))
                existing.image_url = row.get('imageurl', row.get('image_url', ''))
                existing.price_eur = price_eur
                existing.category1 = row.get('category1_code', row.get('category1', ''))
                existing.category2 = row.get('category2_code', row.get('category2', ''))
                existing.category3 = row.get('category3_code', row.get('category3', ''))
                existing.is_discount = row.get('flg_discount', row.get('is_discount', '0')) in ('1', 'true', 'True')
                existing.stock = stock
                existing.rag_indexed = False
                updated += 1
            else:
                new_product = ProductModel(
                    sku=sku,
                    name=name,
                    url=row.get('itemurl', row.get('url', '')),
                    image_url=row.get('imageurl', row.get('image_url', '')),
                    price_eur=price_eur,
                    category1=row.get('category1_code', row.get('category1', '')),
                    category2=row.get('category2_code', row.get('category2', '')),
                    category3=row.get('category3_code', row.get('category3', '')),
                    is_discount=row.get('flg_discount', row.get('is_discount', '0')) in ('1', 'true', 'True'),
                    stock=stock,
                    rag_indexed=False,
                )
                db.add(new_product)
                imported += 1
                
        except Exception as e:
            errors.append(f"Row {row_num}: {str(e)}")
    
    db.commit()
    
    global _rag_index_needs_rebuild
    _rag_index_needs_rebuild = True
    
    return {
        "imported": imported,
        "updated": updated,
        "errors": errors[:10],
        "total_processed": imported + updated,
        "needs_rag_rebuild": True
    }


@router.post("/products/rebuild-rag", response_model=dict)
async def rebuild_rag_index(db: Session = Depends(get_db)):
    """Rebuild the RAG index from database products."""
    global _rag_index_needs_rebuild
    
    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np
        
        logger.info("Starting RAG index rebuild...")
        
        products = db.query(ProductModel).filter(ProductModel.stock > 0).all()
        
        if not products:
            return {"error": "No products with stock > 0", "rebuilt": False}
        
        model = SentenceTransformer('all-MiniLM-L6-v2')
        
        texts = [p.name for p in products]
        embeddings = model.encode(texts, show_progress_bar=True)
        
        embeddings_normalized = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
        
        data = {
            "df": None,
            "embeddings": embeddings_normalized,
            "product_skus": [p.sku for p in products],
            "product_names": [p.name for p in products],
            "product_prices": [p.price_eur for p in products],
            "product_categories": [p.category1 for p in products],
            "product_urls": [p.url for p in products],
            "product_images": [p.image_url for p in products],
        }
        
        os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
        with open(INDEX_PATH, "wb") as f:
            pickle.dump(data, f)
        
        for p in products:
            p.rag_indexed = True
        db.commit()
        
        _rag_index_needs_rebuild = False
        
        return {
            "rebuilt": True,
            "products_indexed": len(products),
            "embedding_dim": embeddings.shape[1],
            "index_path": str(INDEX_PATH)
        }
        
    except Exception as e:
        logger.error(f"RAG rebuild failed: {e}")
        return {"error": str(e), "rebuilt": False}


@router.get("/products/rag-status", response_model=dict)
async def get_rag_status():
    """Get RAG index status."""
    global _rag_index_needs_rebuild
    
    index_exists = INDEX_PATH.exists()
    index_size = 0
    if index_exists:
        index_size = INDEX_PATH.stat().st_size
    
    return {
        "needs_rebuild": _rag_index_needs_rebuild,
        "index_exists": index_exists,
        "index_size_bytes": index_size,
    }


@router.post("/products/{sku}/stock/batch", response_model=dict)
async def batch_update_stock(sku: str, adjustment: int = Query(...), db: Session = Depends(get_db)):
    """Adjust stock by a delta amount."""
    product = db.query(ProductModel).filter(ProductModel.sku == sku).first()
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {sku} not found")
    
    new_stock = product.stock + adjustment
    if new_stock < 0:
        raise HTTPException(status_code=400, detail="Stock cannot go negative")
    
    product.stock = new_stock
    db.commit()
    
    return {
        "sku": sku, 
        "previous_stock": product.stock - adjustment, 
        "adjustment": adjustment, 
        "new_stock": new_stock
    }


@router.get("/products/search-rag", response_model=dict)
async def search_products_rag(
    query: str = Query(..., description="Search query"),
    top_k: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """Search products using RAG (semantic search)."""
    if not INDEX_PATH.exists():
        raise HTTPException(status_code=400, detail="RAG index not built. Run /products/rebuild-rag first.")
    
    try:
        with open(INDEX_PATH, "rb") as f:
            data = pickle.load(f)
        
        from sentence_transformers import SentenceTransformer
        import numpy as np
        
        model = SentenceTransformer('all-MiniLM-L6-v2')
        query_embedding = model.encode([query])
        query_embedding = query_embedding / np.linalg.norm(query_embedding, axis=1, keepdims=True)
        
        embeddings = data.get("embeddings")
        if embeddings is None:
            raise HTTPException(status_code=400, detail="Invalid RAG index format")
        
        similarities = np.dot(embeddings, query_embedding.T).flatten()
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            results.append({
                "sku": data["product_skus"][idx],
                "name": data["product_names"][idx],
                "price_eur": data["product_prices"][idx],
                "category": data["product_categories"][idx],
                "url": data["product_urls"][idx],
                "image_url": data["product_images"][idx],
                "score": float(similarities[idx]),
            })
        
        return {"query": query, "results": results}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
