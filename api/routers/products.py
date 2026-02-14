"""
Products router - Browse product catalog with images and stock.
"""

import os
import sys
import logging
import pickle
from typing import Optional, List
from pathlib import Path

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from fastapi.responses import JSONResponse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

logger = logging.getLogger("lvmh-api.products")
router = APIRouter()

INDEX_PATH = Path(__file__).parent.parent.parent / "data" / "vector_store" / "lv_index.pkl"

_cache = None
_stock_overrides = {}  # In-memory stock overrides


def _load_products():
    """Load products from the vector store index."""
    global _cache
    if _cache is not None:
        return _cache
    
    if not INDEX_PATH.exists():
        logger.warning(f"Vector index not found at {INDEX_PATH}")
        return None
    
    try:
        with open(INDEX_PATH, "rb") as f:
            data = pickle.load(f)
            df = data.get("df")
            if df is not None:
                _cache = df
                return df
    except Exception as e:
        logger.error(f"Failed to load products: {e}")
    return None


class Product(BaseModel):
    sku: str
    name: str
    url: str
    image_url: str
    price_eur: float
    category1: Optional[str] = None
    category2: Optional[str] = None
    category3: Optional[str] = None
    is_discount: bool = False
    stock: int = 10


@router.get("/products")
async def get_products(
    category: Optional[str] = Query(None, description="Filter by category (bags, small_leather_goods, watches, etc.)"),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    search: Optional[str] = Query(None, description="Search in product name"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100)
):
    """
    Get products with pagination and filters.
    Returns product details including image URLs.
    """
    df = _load_products()
    
    if df is None or df.empty:
        return JSONResponse(
            content={"products": [], "total": 0, "page": page, "limit": limit},
            status_code=200
        )
    
    # Apply filters
    filtered = df.copy()
    
    if category:
        filtered = filtered[filtered['category1_code'].str.lower() == category.lower()]
    
    if min_price is not None:
        filtered = filtered[filtered['price_eur'] >= min_price]
    
    if max_price is not None:
        filtered = filtered[filtered['price_eur'] <= max_price]
    
    if search:
        filtered = filtered[filtered['title'].str.contains(search, case=False, na=False)]
    
    total = len(filtered)
    
    # Paginate
    start = (page - 1) * limit
    end = start + limit
    page_data = filtered.iloc[start:end]
    
    products = []
    for _, row in page_data.iterrows():
        sku = row.get("product_code", "")
        stock = _stock_overrides.get(sku, 10)  # Default 10, or custom if set
        products.append({
            "sku": sku,
            "name": row.get("title", ""),
            "url": row.get("itemurl", ""),
            "image_url": row.get("imageurl", ""),
            "price_eur": row.get("price_eur", 0) or 0,
            "category1": row.get("category1_code", ""),
            "category2": row.get("category2_code", ""),
            "category3": row.get("category3_code", ""),
            "is_discount": bool(row.get("flg_discount", 0)),
            "stock": stock,
        })
    
    return {
        "products": products,
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": (total + limit - 1) // limit
    }


@router.get("/products/categories")
async def get_categories():
    """
    Get all available product categories.
    """
    df = _load_products()
    
    if df is None or df.empty:
        return {"categories": []}
    
    categories = df['category1_code'].dropna().unique().tolist()
    categories = [c for c in categories if c]
    categories.sort()
    
    return {"categories": categories}


@router.get("/products/stats")
async def get_product_stats():
    """
    Get product catalog statistics.
    """
    df = _load_products()
    
    if df is None or df.empty:
        return {"total": 0, "categories": {}}
    
    total = len(df)
    category_counts = df['category1_code'].value_counts().to_dict()
    avg_price = df['price_eur'].mean()
    min_price = df['price_eur'].min()
    max_price = df['price_eur'].max()
    discount_count = int(df['flg_discount'].sum())
    
    return {
        "total": total,
        "categories": category_counts,
        "avg_price_eur": round(avg_price, 2) if avg_price else 0,
        "min_price_eur": min_price if min_price else 0,
        "max_price_eur": max_price if max_price else 0,
        "discount_count": discount_count,
    }


# In-memory stock management (would be replaced by DB in production)
_stock_overrides = {}


@router.put("/products/{sku}/stock")
async def update_product_stock(sku: str, stock: int = Query(..., ge=0)):
    """
    Update stock for a specific product.
    """
    if stock < 0:
        raise HTTPException(status_code=400, detail="Stock cannot be negative")
    
    _stock_overrides[sku] = stock
    return {"sku": sku, "stock": stock, "updated": True}


@router.post("/products/{sku}/stock/batch")
async def batch_update_stock(sku: str, adjustment: int = Query(...)):
    """
    Adjust stock by a delta amount (positive or negative).
    """
    current = _stock_overrides.get(sku, 10)
    new_stock = current + adjustment
    
    if new_stock < 0:
        raise HTTPException(status_code=400, detail="Stock cannot go negative")
    
    _stock_overrides[sku] = new_stock
    return {"sku": sku, "previous_stock": current, "adjustment": adjustment, "new_stock": new_stock}


@router.get("/products/stock/overrides")
async def get_stock_overrides():
    """
    Get all stock overrides.
    """
    return {"overrides": _stock_overrides}


@router.delete("/products/{sku}/stock")
async def reset_product_stock(sku: str):
    """
    Reset stock to default (10).
    """
    if sku in _stock_overrides:
        del _stock_overrides[sku]
    return {"sku": sku, "stock": 10, "reset": True}
