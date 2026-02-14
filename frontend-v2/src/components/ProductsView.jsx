import React, { useEffect, useState } from 'react'
import {
    ArrowLeft,
    Search,
    ChevronLeft,
    ChevronRight,
    ShoppingBag,
    Filter,
    Grid3X3,
    List,
    Package,
    RefreshCcw,
    Edit2,
    Check,
    X,
    PackageCheck
} from 'lucide-react'
import { apiFetch } from '../lib/api'
import { useAuth } from '../context/AuthContext'

export default function ProductsView({ onBack }) {
    const { user } = useAuth()
    const [products, setProducts] = useState([])
    const [productsTotal, setProductsTotal] = useState(0)
    const [productsPage, setProductsPage] = useState(1)
    const [productsLoading, setProductsLoading] = useState(false)
    const [productsCategory, setProductsCategory] = useState('')
    const [productsSearch, setProductsSearch] = useState('')
    const [productStats, setProductStats] = useState(null)
    const [viewMode, setViewMode] = useState('grid')
    const [minPrice, setMinPrice] = useState('')
    const [maxPrice, setMaxPrice] = useState('')
    const [editingStock, setEditingStock] = useState(null)
    const [stockValue, setStockValue] = useState('')
    const [stockSaving, setStockSaving] = useState(false)

    const fetchProductStats = async () => {
        try {
            const response = await apiFetch('/api/products/stats')
            if (response.ok) {
                const data = await response.json()
                setProductStats(data)
            }
        } catch (e) {
            console.error('Failed to fetch product stats:', e)
        }
    }

    const fetchProducts = async (page = 1) => {
        setProductsLoading(true)
        try {
            const params = new URLSearchParams()
            params.set('page', String(page))
            params.set('limit', '24')
            if (productsCategory) params.set('category', productsCategory)
            if (productsSearch) params.set('search', productsSearch)
            if (minPrice) params.set('min_price', minPrice)
            if (maxPrice) params.set('max_price', maxPrice)
            
            const response = await apiFetch(`/api/products?${params}`)
            if (response.ok) {
                const data = await response.json()
                setProducts(data.products || [])
                setProductsTotal(data.total || 0)
                setProductsPage(data.page || 1)
            }
        } catch (e) {
            console.error('Failed to fetch products:', e)
        } finally {
            setProductsLoading(false)
        }
    }

    useEffect(() => {
        fetchProductStats()
        fetchProducts()
    }, [])

    const handleSearch = (e) => {
        e.preventDefault()
        setProductsPage(1)
        fetchProducts(1)
    }

    const handleCategoryChange = (cat) => {
        setProductsCategory(cat)
        setProductsPage(1)
        fetchProducts(1)
    }

    const startEditStock = (sku, currentStock) => {
        setEditingStock(sku)
        setStockValue(String(currentStock))
    }

    const cancelEditStock = () => {
        setEditingStock(null)
        setStockValue('')
    }

    const saveStock = async (sku) => {
        const newStock = parseInt(stockValue, 10)
        if (isNaN(newStock) || newStock < 0) {
            return
        }
        setStockSaving(true)
        try {
            const response = await apiFetch(`/api/products/${sku}/stock?stock=${newStock}`, {
                method: 'PUT'
            })
            if (response.ok) {
                setProducts(products.map(p => 
                    p.sku === sku ? { ...p, stock: newStock } : p
                ))
            }
        } catch (e) {
            console.error('Failed to update stock:', e)
        } finally {
            setStockSaving(false)
            setEditingStock(null)
            setStockValue('')
        }
    }

    const totalPages = Math.ceil(productsTotal / 24)

    return (
        <div className="min-h-screen bg-black text-white">
            <div className="border-b border-white/10">
                <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <button
                            onClick={onBack}
                            className="p-2 rounded-lg border border-white/10 hover:border-lvmh-gold/40 hover:text-lvmh-gold transition-colors"
                        >
                            <ArrowLeft size={20} />
                        </button>
                        <div>
                            <h1 className="text-xl font-display font-bold flex items-center gap-2">
                                <ShoppingBag className="text-lvmh-gold" />
                                Product Catalog
                            </h1>
                            <p className="text-xs text-lvmh-gray">
                                {productStats?.total || 0} products available
                            </p>
                        </div>
                    </div>
                    <button
                        onClick={() => fetchProducts(productsPage)}
                        className="p-2 rounded-lg border border-white/10 hover:border-lvmh-gold/40 hover:text-lvmh-gold transition-colors"
                    >
                        <RefreshCcw size={18} />
                    </button>
                </div>
            </div>

            <div className="max-w-7xl mx-auto px-4 py-6">
                <div className="flex flex-wrap gap-4 mb-6">
                    <form onSubmit={handleSearch} className="flex items-center gap-2 flex-1 min-w-[300px]">
                        <div className="relative flex-1">
                            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-lvmh-gray" />
                            <input
                                type="text"
                                placeholder="Search products..."
                                value={productsSearch}
                                onChange={(e) => setProductsSearch(e.target.value)}
                                className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-white/10 bg-white/5 text-white placeholder-lvmh-gray focus:border-lvmh-gold/50 focus:outline-none"
                            />
                        </div>
                        <button
                            type="submit"
                            className="px-4 py-2.5 rounded-lg bg-lvmh-gold text-black font-semibold text-sm hover:bg-lvmh-gold/90 transition-colors"
                        >
                            Search
                        </button>
                    </form>

                    <div className="flex items-center gap-2">
                        <input
                            type="number"
                            placeholder="Min €"
                            value={minPrice}
                            onChange={(e) => setMinPrice(e.target.value)}
                            className="w-24 px-3 py-2.5 rounded-lg border border-white/10 bg-white/5 text-white placeholder-lvmh-gray focus:border-lvmh-gold/50 focus:outline-none text-sm"
                        />
                        <span className="text-lvmh-gray">-</span>
                        <input
                            type="number"
                            placeholder="Max €"
                            value={maxPrice}
                            onChange={(e) => setMaxPrice(e.target.value)}
                            className="w-24 px-3 py-2.5 rounded-lg border border-white/10 bg-white/5 text-white placeholder-lvmh-gray focus:border-lvmh-gold/50 focus:outline-none text-sm"
                        />
                        <button
                            onClick={() => { setProductsPage(1); fetchProducts(1); }}
                            className="px-3 py-2.5 rounded-lg border border-white/10 text-sm hover:border-lvmh-gold/40 hover:text-lvmh-gold transition-colors"
                        >
                            Apply
                        </button>
                    </div>

                    <div className="flex items-center gap-1 border border-white/10 rounded-lg p-1">
                        <button
                            onClick={() => setViewMode('grid')}
                            className={`p-2 rounded ${viewMode === 'grid' ? 'bg-white/10 text-lvmh-gold' : 'text-lvmh-gray hover:text-white'}`}
                        >
                            <Grid3X3 size={18} />
                        </button>
                        <button
                            onClick={() => setViewMode('list')}
                            className={`p-2 rounded ${viewMode === 'list' ? 'bg-white/10 text-lvmh-gold' : 'text-lvmh-gray hover:text-white'}`}
                        >
                            <List size={18} />
                        </button>
                    </div>
                </div>

                <div className="flex gap-6">
                    <div className="w-48 flex-shrink-0">
                        <div className="glass rounded-xl p-4 sticky top-4">
                            <h3 className="text-sm font-semibold mb-3 flex items-center gap-2">
                                <Filter size={14} className="text-lvmh-gold" />
                                Categories
                            </h3>
                            <div className="space-y-1">
                                <button
                                    onClick={() => handleCategoryChange('')}
                                    className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${!productsCategory ? 'bg-lvmh-gold/20 text-lvmh-gold border border-lvmh-gold/30' : 'hover:bg-white/5 text-lvmh-gray hover:text-white'}`}
                                >
                                    All Products
                                </button>
                                {Object.entries(productStats?.categories || {}).map(([cat, count]) => (
                                    <button
                                        key={cat}
                                        onClick={() => handleCategoryChange(cat)}
                                        className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-colors ${productsCategory === cat ? 'bg-lvmh-gold/20 text-lvmh-gold border border-lvmh-gold/30' : 'hover:bg-white/5 text-lvmh-gray hover:text-white'}`}
                                    >
                                        {cat} ({count})
                                    </button>
                                ))}
                            </div>

                            <div className="mt-6 pt-4 border-t border-white/10">
                                <h3 className="text-sm font-semibold mb-3">Stats</h3>
                                <div className="space-y-2 text-xs">
                                    <div className="flex justify-between">
                                        <span className="text-lvmh-gray">Min Price</span>
                                        <span>{productStats?.min_price_eur?.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })}</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-lvmh-gray">Max Price</span>
                                        <span>{productStats?.max_price_eur?.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })}</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-lvmh-gray">Avg Price</span>
                                        <span>{productStats?.avg_price_eur?.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })}</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span className="text-lvmh-gray">On Sale</span>
                                        <span className="text-green-400">{productStats?.discount_count || 0}</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="flex-1">
                        {productsLoading ? (
                            <div className="text-center py-12 text-lvmh-gray">Loading products...</div>
                        ) : products.length === 0 ? (
                            <div className="text-center py-12 text-lvmh-gray">No products found.</div>
                        ) : viewMode === 'grid' ? (
                            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                                {products.map((product, idx) => (
                                    <a
                                        key={product.sku || idx}
                                        href={product.url}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="glass rounded-xl overflow-hidden hover:border-lvmh-gold/50 transition-all hover:scale-[1.02]"
                                    >
                                        <div className="aspect-square bg-white/5 relative">
                                            {product.image_url ? (
                                                <img 
                                                    src={product.image_url} 
                                                    alt={product.name}
                                                    className="w-full h-full object-cover"
                                                    onError={(e) => { e.target.style.display = 'none'; }}
                                                />
                                            ) : (
                                                <div className="w-full h-full flex items-center justify-center text-lvmh-gray">
                                                    <Package size={32} />
                                                </div>
                                            )}
                                            {product.is_discount && (
                                                <span className="absolute top-2 right-2 px-2 py-1 bg-red-500 text-white text-[10px] font-bold rounded">
                                                    SALE
                                                </span>
                                            )}
                                        </div>
                                        <div className="p-3">
                                            <div className="text-[10px] text-lvmh-gray mb-1">{product.sku}</div>
                                            <div className="text-sm font-medium line-clamp-2 min-h-[2.5rem]" title={product.name}>
                                                {product.name}
                                            </div>
                                            <div className="text-sm text-lvmh-gold font-bold mt-2">
                                                {product.price_eur?.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })}
                                            </div>
                                            {product.category1 && (
                                                <div className="text-[10px] text-lvmh-gray mt-2 uppercase tracking-wider">
                                                    {product.category1}
                                                </div>
                                            )}
                                            <div className="mt-2 flex items-center gap-2">
                                                {editingStock === product.sku ? (
                                                    <div className="flex items-center gap-1">
                                                        <input
                                                            type="number"
                                                            value={stockValue}
                                                            onChange={(e) => setStockValue(e.target.value)}
                                                            className="w-14 px-2 py-1 rounded bg-white/10 border border-white/20 text-xs text-white"
                                                            min="0"
                                                        />
                                                        <button
                                                            onClick={(e) => { e.preventDefault(); saveStock(product.sku); }}
                                                            disabled={stockSaving}
                                                            className="p-1 rounded bg-green-500/20 text-green-400 hover:bg-green-500/30"
                                                        >
                                                            <Check size={12} />
                                                        </button>
                                                        <button
                                                            onClick={(e) => { e.preventDefault(); cancelEditStock(); }}
                                                            className="p-1 rounded bg-red-500/20 text-red-400 hover:bg-red-500/30"
                                                        >
                                                            <X size={12} />
                                                        </button>
                                                    </div>
                                                ) : (
                                                    <button
                                                        onClick={(e) => { e.preventDefault(); startEditStock(product.sku, product.stock); }}
                                                        className="flex items-center gap-1 text-[10px] text-lvmh-gray hover:text-lvmh-gold transition-colors"
                                                    >
                                                        <PackageCheck size={12} />
                                                        <span>Stock: {product.stock}</span>
                                                        <Edit2 size={10} />
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    </a>
                                ))}
                            </div>
                        ) : (
                            <div className="space-y-2">
                                {products.map((product, idx) => (
                                    <a
                                        key={product.sku || idx}
                                        href={product.url}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="glass rounded-lg p-3 flex items-center gap-4 hover:border-lvmh-gold/50 transition-colors"
                                    >
                                        <div className="w-16 h-16 bg-white/5 rounded-lg flex-shrink-0 overflow-hidden">
                                            {product.image_url ? (
                                                <img 
                                                    src={product.image_url} 
                                                    alt={product.name}
                                                    className="w-full h-full object-cover"
                                                    onError={(e) => { e.target.style.display = 'none'; }}
                                                />
                                            ) : (
                                                <div className="w-full h-full flex items-center justify-center text-lvmh-gray">
                                                    <Package size={20} />
                                                </div>
                                            )}
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <div className="text-xs text-lvmh-gray">{product.sku}</div>
                                            <div className="text-sm font-medium truncate">{product.name}</div>
                                            <div className="text-xs text-lvmh-gray">{product.category1}</div>
                                        </div>
                                        <div className="text-right">
                                            <div className="text-sm text-lvmh-gold font-bold">
                                                {product.price_eur?.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })}
                                            </div>
                                            {product.is_discount && (
                                                <span className="text-[10px] text-red-400">On Sale</span>
                                            )}
                                            <div className="text-[10px] text-lvmh-gray mt-1">
                                                Stock: {product.stock}
                                            </div>
                                        </div>
                                    </a>
                                ))}
                            </div>
                        )}

                        {totalPages > 1 && (
                            <div className="flex items-center justify-center gap-3 mt-8">
                                <button
                                    onClick={() => { const p = Math.max(1, productsPage - 1); setProductsPage(p); fetchProducts(p); }}
                                    disabled={productsPage === 1}
                                    className="p-2 rounded-lg border border-white/10 hover:border-lvmh-gold/40 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    <ChevronLeft size={20} />
                                </button>
                                <span className="text-sm text-lvmh-gray">
                                    Page {productsPage} of {totalPages}
                                </span>
                                <button
                                    onClick={() => { const p = productsPage + 1; setProductsPage(p); fetchProducts(p); }}
                                    disabled={productsPage >= totalPages}
                                    className="p-2 rounded-lg border border-white/10 hover:border-lvmh-gold/40 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    <ChevronRight size={20} />
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    )
}
