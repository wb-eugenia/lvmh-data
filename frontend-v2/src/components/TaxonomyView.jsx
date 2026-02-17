import React, { useEffect, useState } from 'react'
import { ChevronDown, ChevronRight, Search, Download, Info } from 'lucide-react'
import { apiFetch } from '../lib/api'

const PILLAR_LABELS = {
    "1_produit": "Produit",
    "2_profil": "Profil Client",
    "3_hospitalite": "Hospitalité & Care",
    "4_actions": "Actions Business"
}

const PILLAR_COLORS = {
    "1_produit": "text-blue-400",
    "2_profil": "text-purple-400",
    "3_hospitalite": "text-green-400",
    "4_actions": "text-gold"
}

export default function TaxonomyView() {
    const [taxonomy, setTaxonomy] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)
    const [search, setSearch] = useState('')
    const [expandedPillars, setExpandedPillars] = useState({})
    const [expandedCategories, setExpandedCategories] = useState({})

    useEffect(() => {
        apiFetch('/api/dashboard/taxonomy')
            .then(res => res.json())
            .then(data => {
                setTaxonomy(data.taxonomy)
                const initialExpanded = {}
                Object.keys(data.taxonomy).forEach(pillar => {
                    initialExpanded[pillar] = true
                })
                setExpandedPillars(initialExpanded)
            })
            .catch(err => setError(err.message))
            .finally(() => setLoading(false))
    }, [])

    const togglePillar = (pillar) => {
        setExpandedPillars(prev => ({ ...prev, [pillar]: !prev[pillar] }))
    }

    const toggleCategory = (key) => {
        setExpandedCategories(prev => ({ ...prev, [key]: !prev[key] }))
    }

    const filterTags = (tags) => {
        if (!search) return tags
        return tags.filter(t => 
            t.toLowerCase().includes(search.toLowerCase())
        )
    }

    const getTotalTags = () => {
        if (!taxonomy) return 0
        let total = 0
        Object.values(taxonomy).forEach(pillar => {
            Object.values(pillar).forEach(cats => {
                total += cats.length
            })
        })
        return total
    }

    const handleExport = () => {
        const data = {
            taxonomy,
            version: "2.2",
            exported_at: new Date().toISOString()
        }
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `lvmh-taxonomy-${new Date().toISOString().split('T')[0]}.json`
        a.click()
        URL.revokeObjectURL(url)
    }

    if (loading) {
        return (
            <div className="glass p-8 flex items-center justify-center">
                <div className="text-lvmh-gray">Chargement taxonomie...</div>
            </div>
        )
    }

    if (error) {
        return (
            <div className="glass p-6 border border-red-500/30 bg-red-500/10 text-red-200">
                Erreur: {error}
            </div>
        )
    }

    return (
        <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                    <h2 className="text-xl font-display font-black gold-text">
                        Taxonomie LVMH
                    </h2>
                    <p className="text-xs uppercase tracking-widest text-lvmh-gray mt-1">
                        Architecture 4 piliers • {getTotalTags()} tags total
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <button
                        onClick={handleExport}
                        className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-white/10 text-xs uppercase tracking-widest hover:border-silver/40 hover:text-silver transition-colors"
                    >
                        <Download size={12} />
                        Export JSON
                    </button>
                </div>
            </div>

            <div className="glass p-4 flex items-center gap-3">
                <Search size={16} className="text-lvmh-gray" />
                <input
                    type="text"
                    placeholder="Rechercher un tag..."
                    className="bg-transparent flex-1 outline-none text-white placeholder-lvmh-gray text-sm"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                />
                {search && (
                    <button
                        onClick={() => setSearch('')}
                        className="text-xs text-lvmh-gray hover:text-white"
                    >
                        Effacer
                    </button>
                )}
            </div>

            {taxonomy && (
                <div className="space-y-4">
                    {Object.entries(taxonomy).map(([pillar, categories]) => (
                        <div key={pillar} className="glass overflow-hidden">
                            <button
                                onClick={() => togglePillar(pillar)}
                                className="w-full p-4 flex items-center justify-between hover:bg-white/5 transition"
                            >
                                <div className="flex items-center gap-3">
                                    {expandedPillars[pillar] ? (
                                        <ChevronDown size={18} className={PILLAR_COLORS[pillar]} />
                                    ) : (
                                        <ChevronRight size={18} className={PILLAR_COLORS[pillar]} />
                                    )}
                                    <span className={`text-lg font-semibold ${PILLAR_COLORS[pillar]}`}>
                                        Pilier {pillar.split('_')[0]} — {PILLAR_LABELS[pillar]}
                                    </span>
                                </div>
                                <span className="text-xs text-lvmh-gray">
                                    {Object.keys(categories).length} catégories
                                </span>
                            </button>

                            {expandedPillars[pillar] && (
                                <div className="p-4 pt-0 space-y-4">
                                    {Object.entries(categories).map(([category, tags]) => {
                                        const categoryKey = `${pillar}_${category}`
                                        const filteredTags = filterTags(tags)
                                        
                                        return (
                                            <div key={category}>
                                                <button
                                                    onClick={() => toggleCategory(categoryKey)}
                                                    className="flex items-center gap-2 mb-2 hover:text-white transition"
                                                >
                                                    {expandedCategories[categoryKey] ? (
                                                        <ChevronDown size={14} className="text-lvmh-gray" />
                                                    ) : (
                                                        <ChevronRight size={14} className="text-lvmh-gray" />
                                                    )}
                                                    <span className="text-sm font-medium text-gray-300 capitalize">
                                                        {category}
                                                    </span>
                                                    <span className="text-xs text-lvmh-gray">
                                                        ({tags.length} tags)
                                                    </span>
                                                    {search && filteredTags.length !== tags.length && (
                                                        <span className="text-xs text-silver">
                                                            ({filteredTags.length} / {tags.length})
                                                        </span>
                                                    )}
                                                </button>

                                                {expandedCategories[categoryKey] && (
                                                    <div className="ml-6 flex flex-wrap gap-2">
                                                        {filteredTags.length > 0 ? (
                                                            filteredTags.map(tag => (
                                                                <span
                                                                    key={tag}
                                                                    className="px-3 py-1 bg-white/5 border border-white/10 rounded-lg text-xs text-gray-300 hover:border-silver/30 hover:text-white transition cursor-default"
                                                                >
                                                                    {tag}
                                                                </span>
                                                            ))
                                                        ) : (
                                                            <span className="text-xs text-lvmh-gray italic">
                                                                Aucun résultat
                                                            </span>
                                                        )}
                                                    </div>
                                                )}
                                            </div>
                                        )
                                    })}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}

            <div className="glass p-4 flex items-start gap-3">
                <Info size={16} className="text-lvmh-gray mt-0.5 flex-shrink-0" />
                <div className="text-xs text-lvmh-gray">
                    <p>Stats de mentions (fréquence d'utilisation) disponibles bientôt.</p>
                    <p className="mt-1">Pour modifier la taxonomie: Export JSON → Modifier → Contacter l'équipe Data.</p>
                </div>
            </div>
        </div>
    )
}
