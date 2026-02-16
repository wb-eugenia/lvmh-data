import React, { useState, useEffect, useRef } from 'react'
import { ChevronLeft, ChevronRight, Minus, Plus, RefreshCw, Search, ShoppingBag, Trash2, X, Upload } from 'lucide-react'
import { apiFetch } from '../lib/api'

export default function AdminProductsView() {
    const [products, setProducts] = useState([])
    const [total, setTotal] = useState(0)
    const [page, setPage] = useState(1)
    const [search, setSearch] = useState('')
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [showAddModal, setShowAddModal] = useState(false)
    const [showImportModal, setShowImportModal] = useState(false)
    const [newProduct, setNewProduct] = useState({ sku: '', name: '', price_eur: 0, category1: '', stock: 10, image_url: '' })
    const [ragRebuilding, setRagRebuilding] = useState(false)
    const [importing, setImporting] = useState(false)
    const [importResult, setImportResult] = useState(null)
    const [batches, setBatches] = useState([])
    const fileInputRef = useRef(null)

    const fetchProducts = async (pageNum = 1) => {
        setLoading(true)
        setError(null)
        try {
            const params = new URLSearchParams()
            params.set('page', String(pageNum))
            params.set('limit', '12')
            if (search) params.set('search', search)
            
            console.log('Fetching products from /api/products...')
            const res = await apiFetch(`/api/products?${params}`)
            console.log('Response status:', res.status)
            
            if (res.ok) {
                const data = await res.json()
                console.log('Products data:', data)
                setProducts(data.products || [])
                setTotal(data.total || 0)
                setPage(data.page || 1)
            } else {
                const text = await res.text()
                setError(`Erreur: ${res.status} - ${text}`)
            }
        } catch (e) {
            setError('Erreur de connexion: ' + e.message)
            console.error('Failed to fetch products:', e)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchProducts()
    }, [])

    useEffect(() => {
        if (showImportModal) {
            fetchBatches()
        }
    }, [showImportModal])

    const fetchBatches = async () => {
        try {
            const res = await apiFetch('/api/products/batches')
            if (res.ok) {
                const data = await res.json()
                setBatches(data.batches || [])
            }
        } catch (e) {
            console.error('Failed to fetch batches:', e)
        }
    }

    const handleImportCSV = async (e) => {
        const file = e.target.files?.[0]
        if (!file) return
        
        setImporting(true)
        setImportResult(null)
        
        try {
            const formData = new FormData()
            formData.append('file', file)
            
            const res = await apiFetch('/api/products/upload-csv', {
                method: 'POST',
                body: formData,
            })
            
            const data = await res.json()
            setImportResult(data)
            
            if (data.batch_id) {
                fetchBatches()
            }
        } catch (err) {
            setImportResult({ error: err.message })
        } finally {
            setImporting(false)
            if (fileInputRef.current) {
                fileInputRef.current.value = ''
            }
        }
    }

    const handleSearch = (e) => {
        e.preventDefault()
        fetchProducts(1)
    }

    const handleDelete = async (sku) => {
        if (!confirm(`Supprimer le produit ${sku}?`)) return
        try {
            const res = await apiFetch(`/api/products/${sku}`, { method: 'DELETE' })
            if (res.ok) {
                fetchProducts(page)
            }
        } catch (e) {
            console.error('Delete failed:', e)
        }
    }

    const handleStockChange = async (sku, newStock) => {
        try {
            const res = await apiFetch(`/api/products/${sku}/stock?stock=${newStock}`, { method: 'PUT' })
            if (res.ok) {
                fetchProducts(page)
            }
        } catch (e) {
            console.error('Stock update failed:', e)
        }
    }

    const handleAddProduct = async (e) => {
        e.preventDefault()
        try {
            const res = await apiFetch('/api/products', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newProduct)
            })
            if (res.ok) {
                setShowAddModal(false)
                setNewProduct({ sku: '', name: '', price_eur: 0, category1: '', stock: 10, image_url: '' })
                fetchProducts(1)
            } else {
                const err = await res.text()
                alert('Erreur: ' + err)
            }
        } catch (e) {
            console.error('Add failed:', e)
        }
    }

    const handleRebuildRag = async () => {
        setRagRebuilding(true)
        try {
            const res = await apiFetch('/api/products/rebuild-rag', { method: 'POST' })
            const data = await res.json()
            alert(data.rebuilt ? `RAG rebuild OK: ${data.products_indexed} produits indexés` : 'Erreur: ' + data.error)
        } catch (e) {
            alert('RAG rebuild failed')
        } finally {
            setRagRebuilding(false)
        }
    }

    const totalPages = Math.ceil(total / 12)

    return (
        <div className="space-y-6">
            <div className="glass p-6">
                <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
                    <h3 className="text-lg font-bold flex items-center gap-2">
                        <ShoppingBag size={18} className="text-lvmh-gold" />
                        Gestion des Produits
                    </h3>
                    <div className="flex gap-2">
                        <button
                            onClick={() => { fetchBatches(); setShowImportModal(true); }}
                            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-white/10 text-xs hover:border-lvmh-gold/40"
                        >
                            <Upload size={14} />
                            Import CSV
                        </button>
                        <button
                            onClick={handleRebuildRag}
                            disabled={ragRebuilding}
                            className="flex items-center gap-2 px-3 py-2 rounded-lg border border-white/10 text-xs hover:border-lvmh-gold/40 disabled:opacity-50"
                        >
                            <RefreshCw size={14} className={ragRebuilding ? 'animate-spin' : ''} />
                            {ragRebuilding ? 'Rebuilding...' : 'Rebuild RAG'}
                        </button>
                        <button
                            onClick={() => setShowAddModal(true)}
                            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-lvmh-gold text-black text-xs font-bold hover:bg-lvmh-gold/90"
                        >
                            <Plus size={14} />
                            Ajouter Produit
                        </button>
                    </div>
                </div>

                <form onSubmit={handleSearch} className="flex gap-2 mb-4">
                    <div className="relative flex-1">
                        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-lvmh-gray" />
                        <input
                            type="text"
                            placeholder="Rechercher produits..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            className="w-full pl-10 pr-4 py-2 rounded-lg border border-white/10 bg-white/[0.02] text-white placeholder-lvmh-gray focus:outline-none focus:border-lvmh-gold/40"
                        />
                    </div>
                    <button type="submit" className="px-4 py-2 rounded-lg border border-lvmh-gold/40 text-lvmh-gold hover:bg-lvmh-gold/10">
                        Rechercher
                    </button>
                </form>

                {loading ? (
                    <div className="text-center py-8 text-lvmh-gray">Chargement...</div>
                ) : error ? (
                    <div className="text-center py-8 text-red-400">
                        <div className="mb-2">{error}</div>
                        <button onClick={() => fetchProducts()} className="text-xs underline">Reessayer</button>
                    </div>
                ) : products.length > 0 ? (
                    <>
                        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
                            {products.map((product) => (
                                <div key={product.sku} className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                                    <div className="aspect-square bg-white/5 rounded-lg mb-2 flex items-center justify-center overflow-hidden">
                                        {product.image_url ? (
                                            <img src={product.image_url} alt={product.name} className="w-full h-full object-cover" />
                                        ) : (
                                            <ShoppingBag size={32} className="text-lvmh-gray" />
                                        )}
                                    </div>
                                    <div className="font-semibold text-sm truncate">{product.name}</div>
                                    <div className="text-xs text-lvmh-gold">{product.price_eur ? product.price_eur.toFixed(2) + ' €' : '-'}</div>
                                    <div className="text-[10px] text-lvmh-gray uppercase">{product.category1 || 'N/A'}</div>
                                    <div className="flex items-center justify-between mt-2">
                                        <div className="flex items-center gap-1">
                                            <button
                                                onClick={() => handleStockChange(product.sku, Math.max(0, (product.stock || 0) - 1))}
                                                className="p-1 rounded border border-white/10 hover:border-lvmh-gold/40"
                                            >
                                                <Minus size={12} />
                                            </button>
                                            <span className="text-xs px-2">{product.stock || 0}</span>
                                            <button
                                                onClick={() => handleStockChange(product.sku, (product.stock || 0) + 1)}
                                                className="p-1 rounded border border-white/10 hover:border-lvmh-gold/40"
                                            >
                                                <Plus size={12} />
                                            </button>
                                        </div>
                                        <button
                                            onClick={() => handleDelete(product.sku)}
                                            className="p-1 rounded text-red-300 hover:bg-red-500/20"
                                        >
                                            <Trash2 size={14} />
                                        </button>
                                    </div>
                                    {product.rag_indexed && (
                                        <div className="text-[10px] text-green-400 mt-1">RAG indexed</div>
                                    )}
                                </div>
                            ))}
                        </div>

                        {totalPages > 1 && (
                            <div className="flex justify-center gap-2 mt-4">
                                <button
                                    onClick={() => fetchProducts(page - 1)}
                                    disabled={page === 1}
                                    className="px-3 py-1 rounded border border-white/10 disabled:opacity-50"
                                >
                                    <ChevronLeft size={16} />
                                </button>
                                <span className="px-3 py-1 text-sm text-lvmh-gray">
                                    Page {page} / {totalPages}
                                </span>
                                <button
                                    onClick={() => fetchProducts(page + 1)}
                                    disabled={page >= totalPages}
                                    className="px-3 py-1 rounded border border-white/10 disabled:opacity-50"
                                >
                                    <ChevronRight size={16} />
                                </button>
                            </div>
                        )}
                    </>
                ) : (
                    <div className="text-center py-8 text-lvmh-gray">Aucun produit.</div>
                )}
            </div>

            {showAddModal && (
                <div 
                    className="fixed inset-0 bg-black/70 flex items-center justify-center z-[100]"
                    onClick={(e) => e.target === e.currentTarget && setShowAddModal(false)}
                >
                    <div className="glass p-6 rounded-lg w-full max-w-md mx-4">
                        <div className="flex justify-between items-center mb-4">
                            <h3 className="text-lg font-bold">Ajouter un Produit</h3>
                            <button 
                                onClick={() => setShowAddModal(false)} 
                                className="text-lvmh-gray hover:text-white p-1"
                            >
                                <X size={20} />
                            </button>
                        </div>
                        <form onSubmit={handleAddProduct} className="space-y-4">
                            <div>
                                <label className="block text-xs text-lvmh-gray mb-1">SKU</label>
                                <input
                                    type="text"
                                    required
                                    value={newProduct.sku}
                                    onChange={(e) => setNewProduct({ ...newProduct, sku: e.target.value })}
                                    className="w-full px-3 py-2 rounded-lg border border-white/10 bg-white/[0.02] text-white"
                                />
                            </div>
                            <div>
                                <label className="block text-xs text-lvmh-gray mb-1">Nom</label>
                                <input
                                    type="text"
                                    required
                                    value={newProduct.name}
                                    onChange={(e) => setNewProduct({ ...newProduct, name: e.target.value })}
                                    className="w-full px-3 py-2 rounded-lg border border-white/10 bg-white/[0.02] text-white"
                                />
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-xs text-lvmh-gray mb-1">Prix (€)</label>
                                    <input
                                        type="number"
                                        step="0.01"
                                        value={newProduct.price_eur}
                                        onChange={(e) => setNewProduct({ ...newProduct, price_eur: parseFloat(e.target.value) || 0 })}
                                        className="w-full px-3 py-2 rounded-lg border border-white/10 bg-white/[0.02] text-white"
                                    />
                                </div>
                                <div>
                                    <label className="block text-xs text-lvmh-gray mb-1">Stock</label>
                                    <input
                                        type="number"
                                        value={newProduct.stock}
                                        onChange={(e) => setNewProduct({ ...newProduct, stock: parseInt(e.target.value) || 0 })}
                                        className="w-full px-3 py-2 rounded-lg border border-white/10 bg-white/[0.02] text-white"
                                    />
                                </div>
                            </div>
                            <div>
                                <label className="block text-xs text-lvmh-gray mb-1">Catégorie</label>
                                <input
                                    type="text"
                                    value={newProduct.category1}
                                    onChange={(e) => setNewProduct({ ...newProduct, category1: e.target.value })}
                                    className="w-full px-3 py-2 rounded-lg border border-white/10 bg-white/[0.02] text-white"
                                />
                            </div>
                            <div>
                                <label className="block text-xs text-lvmh-gray mb-1">URL Image</label>
                                <input
                                    type="url"
                                    value={newProduct.image_url}
                                    onChange={(e) => setNewProduct({ ...newProduct, image_url: e.target.value })}
                                    className="w-full px-3 py-2 rounded-lg border border-white/10 bg-white/[0.02] text-white"
                                />
                            </div>
                            <button
                                type="submit"
                                className="w-full py-2 rounded-lg bg-lvmh-gold text-black font-bold hover:bg-lvmh-gold/90"
                            >
                                Ajouter
                            </button>
                        </form>
                    </div>
                </div>
            )}

            {showImportModal && (
                <div 
                    className="fixed inset-0 bg-black/70 flex items-center justify-center z-[100]"
                    onClick={(e) => e.target === e.currentTarget && setShowImportModal(false)}
                >
                    <div className="glass p-6 rounded-lg w-full max-w-2xl mx-4 max-h-[80vh] overflow-y-auto">
                        <div className="flex justify-between items-center mb-4">
                            <h3 className="text-lg font-bold flex items-center gap-2">
                                <Upload size={18} className="text-lvmh-gold" />
                                Import CSV
                            </h3>
                            <button 
                                onClick={() => setShowImportModal(false)} 
                                className="text-lvmh-gray hover:text-white p-1"
                            >
                                <X size={20} />
                            </button>
                        </div>

                        <div className="mb-6">
                            <label className="flex flex-col items-center justify-center w-full h-32 border-2 border-dashed border-white/20 rounded-lg cursor-pointer hover:border-lvmh-gold/50 transition-colors">
                                <div className="flex flex-col items-center justify-center pt-5 pb-6">
                                    <Upload size={24} className="text-lvmh-gray mb-2" />
                                    <p className="text-sm text-lvmh-gray">
                                        {importing ? 'Import en cours...' : 'Click to upload CSV'}
                                    </p>
                                    <p className="text-xs text-lvmh-gray mt-1">Max 10MB</p>
                                </div>
                                <input
                                    ref={fileInputRef}
                                    type="file"
                                    accept=".csv"
                                    onChange={handleImportCSV}
                                    disabled={importing}
                                    className="hidden"
                                />
                            </label>
                        </div>

                        {importResult && (
                            <div className={`mb-4 p-3 rounded-lg ${importResult.error ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'}`}>
                                {importResult.batch_id ? `Batch #${importResult.batch_id} - ${importResult.total_rows} rows queued` : importResult.error}
                            </div>
                        )}

                        <div className="border-t border-white/10 pt-4">
                            <h4 className="text-sm font-semibold mb-3">Historique des imports</h4>
                            <div className="space-y-2 max-h-60 overflow-y-auto">
                                {batches.length === 0 ? (
                                    <p className="text-sm text-lvmh-gray">Aucun import.</p>
                                ) : (
                                    batches.map((batch) => (
                                        <div key={batch.id} className="flex items-center justify-between p-3 rounded-lg bg-white/5">
                                            <div>
                                                <div className="text-sm font-medium">{batch.filename}</div>
                                                <div className="text-xs text-lvmh-gray">
                                                    {batch.total_rows} rows • {batch.created_at ? new Date(batch.created_at).toLocaleString('fr-FR') : ''}
                                                </div>
                                            </div>
                                            <div className="text-right">
                                                <span className={`text-xs px-2 py-1 rounded ${
                                                    batch.status === 'completed' ? 'bg-green-500/20 text-green-400' :
                                                    batch.status === 'processing' ? 'bg-yellow-500/20 text-yellow-400' :
                                                    batch.status === 'failed' ? 'bg-red-500/20 text-red-400' :
                                                    'bg-gray-500/20 text-gray-400'
                                                }`}>
                                                    {batch.status}
                                                </span>
                                                <div className="text-xs text-lvmh-gray mt-1">
                                                    +{batch.imported_rows} / ~{batch.updated_rows}
                                                </div>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    )
}
