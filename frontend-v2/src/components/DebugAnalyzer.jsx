import React, { useState } from 'react';
import { Play, Loader2, Terminal, Tag, ShoppingBag, Lightbulb, Brain, Shield, AlertCircle, ChevronDown, ChevronRight, Layers, Users } from 'lucide-react';
import { apiFetch } from '../lib/api';
import { processTextEdge } from '../lib/edge-processor';

export default function DebugAnalyzer() {
    const [inputText, setInputText] = useState('');
    const [language, setLanguage] = useState('FR');
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);
    const [error, setError] = useState(null);
    const [expandedSections, setExpandedSections] = useState({
        extraction: true,
        rag: true,
        nba: true,
        routing: true,
        rgpd: true,
        meta: false
    });

    const toggleSection = (section) => {
        setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
    };

    const analyzeText = async () => {
        if (!inputText.trim()) return;
        
        setLoading(true);
        setError(null);
        setResult(null);

        const startTime = performance.now();

        try {
            const edgeResult = processTextEdge(inputText, language);
            
            const res = await apiFetch('/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: edgeResult.text,
                    text_preprocessed: true,
                    rgpd_risk: edgeResult.rgpd_risk,
                    language: language,
                    client_id: 'DEBUG_' + Date.now()
                })
            });

            const endTime = performance.now();
            const networkTime = Math.round(endTime - startTime);

            if (!res.ok) {
                const errorText = await res.text();
                throw new Error(`HTTP ${res.status}: ${errorText}`);
            }

            const data = await res.json();
            data._networkTime = networkTime;
            setResult(data);
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    const Section = ({ title, icon: Icon, section, children, badge }) => (
        <div className="glass overflow-hidden mb-4">
            <button
                onClick={() => toggleSection(section)}
                className="w-full flex items-center justify-between p-4 hover:bg-white/5 transition-colors"
            >
                <div className="flex items-center gap-3">
                    <Icon size={20} className="text-lvmh-gold" />
                    <span className="font-bold">{title}</span>
                    {badge && (
                        <span className={`text-xs px-2 py-0.5 rounded-full ${badge.color}`}>
                            {badge.text}
                        </span>
                    )}
                </div>
                {expandedSections[section] ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
            </button>
            {expandedSections[section] && (
                <div className="px-4 pb-4 border-t border-white/10 pt-4">
                    {children}
                </div>
            )}
        </div>
    );

    const MetricCard = ({ label, value, color = 'text-white' }) => (
        <div className="bg-white/5 rounded-lg p-3">
            <div className="text-xs text-lvmh-gray uppercase mb-1">{label}</div>
            <div className={`text-lg font-bold ${color}`}>{value}</div>
        </div>
    );

    const formatValue = (value) => {
        if (value === null || value === undefined) return '';
        if (typeof value === 'string') return value;
        if (typeof value === 'number' || typeof value === 'boolean') return String(value);
        if (Array.isArray(value)) return value.map((item) => formatValue(item)).filter(Boolean).join(', ');
        if (typeof value === 'object') {
            if (typeof value.description === 'string' && value.description.trim()) return value.description.trim();
            if (typeof value.label === 'string' && value.label.trim()) return value.label.trim();
            try {
                return JSON.stringify(value);
            } catch {
                return String(value);
            }
        }
        return String(value);
    };

    const normalizePercent = (value) => {
        if (value === null || value === undefined || Number.isNaN(Number(value))) return 0;
        const numeric = Number(value);
        return Math.round(numeric <= 1 ? numeric * 100 : numeric);
    };

    const collectAllTags = (payload) => {
        if (!payload || typeof payload !== 'object') return [];
        const explicit = Array.isArray(payload.tags) ? payload.tags : [];
        const p1 = payload.pilier_1_univers_produit || {};
        const p2 = payload.pilier_2_profil_client || {};
        const p3 = payload.pilier_3_hospitalite_care || {};
        const p4 = payload.pilier_4_action_business || {};

        const derived = [
            ...(Array.isArray(p1.categories) ? p1.categories : []),
            ...(Array.isArray(p1.produits_mentionnes) ? p1.produits_mentionnes : []),
            ...(Array.isArray(p3.allergies?.food) ? p3.allergies.food : []),
            ...(Array.isArray(p3.allergies?.contact) ? p3.allergies.contact : []),
            p2.purchase_context?.behavior,
            p2.purchase_context?.type,
            p3.occasion,
            p4.next_best_action?.action_type ? `action:${p4.next_best_action.action_type}` : null
        ];

        return [...explicit, ...derived]
            .map((item) => String(item || '').trim())
            .filter(Boolean)
            .filter((item, index, array) => array.findIndex((candidate) => candidate.toLowerCase() === item.toLowerCase()) === index);
    };

    const estimateCompleteness = (payload) => {
        if (!payload || typeof payload !== 'object') return 0;
        const p1 = payload.pilier_1_univers_produit || {};
        const p2 = payload.pilier_2_profil_client || {};
        const p3 = payload.pilier_3_hospitalite_care || {};
        const p4 = payload.pilier_4_action_business || {};
        const checks = [
            Boolean(p4.budget_specific || p4.budget_potential),
            Boolean((p1.categories || []).length || (p1.produits_mentionnes || []).length),
            Boolean(p3.occasion),
            Boolean(p2.purchase_context?.type || p2.purchase_context?.behavior),
            Boolean(p4.urgency),
        ];
        const filled = checks.filter(Boolean).length;
        return Math.round((filled / checks.length) * 100);
    };

    const allTags = collectAllTags(result);
    const qualityPercent = normalizePercent(result?.meta_analysis?.quality_score);
    const confidencePercent = normalizePercent(
        result?.meta_analysis?.confidence_score ?? result?.routing?.confidence
    );
    const completenessPercentRaw = normalizePercent(result?.meta_analysis?.completeness_score);
    const completenessPercent = completenessPercentRaw > 0 ? completenessPercentRaw : estimateCompleteness(result);

    return (
        <div className="space-y-6 animate-in fade-in duration-500 max-w-6xl mx-auto">
            {/* Header */}
            <div className="flex justify-between items-center">
                <div>
                    <h3 className="text-2xl font-black gold-text flex items-center gap-2">
                        <Terminal size={24} /> Debug Pipeline
                    </h3>
                    <p className="text-sm text-lvmh-gray mt-1">
                        Entrez une transcription pour voir tous les détails du traitement
                    </p>
                </div>
            </div>

            {/* Input Section */}
            <div className="glass p-6 space-y-4">
                <div className="flex gap-4">
                    <select
                        value={language}
                        onChange={(e) => setLanguage(e.target.value)}
                        className="bg-white/5 border border-white/10 rounded-lg py-3 px-4 text-white focus:ring-1 focus:ring-lvmh-gold"
                    >
                        <option value="FR">🇫🇷 Français</option>
                        <option value="EN">🇬🇧 English</option>
                        <option value="ES">🇪🇸 Español</option>
                        <option value="IT">🇮🇹 Italiano</option>
                        <option value="DE">🇩🇪 Deutsch</option>
                    </select>
                    <button
                        onClick={analyzeText}
                        disabled={loading || !inputText.trim()}
                        className="flex items-center gap-2 bg-lvmh-gold text-black px-6 py-3 rounded-lg font-bold hover:bg-lvmh-gold/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {loading ? <Loader2 size={20} className="animate-spin" /> : <Play size={20} />}
                        {loading ? 'Analyse...' : 'Analyser'}
                    </button>
                </div>

                <textarea
                    value={inputText}
                    onChange={(e) => setInputText(e.target.value)}
                    placeholder="Ex: Mme Dupont cherche un sac noir en cuir pour son anniversaire. Budget 2000€. Elle est cliente VIP depuis 2019..."
                    className="w-full h-32 bg-white/5 border border-white/10 rounded-lg p-4 text-white placeholder-lvmh-gray resize-none focus:ring-1 focus:ring-lvmh-gold transition-all"
                />

                {/* Quick Examples */}
                <div className="flex flex-wrap gap-2">
                    <span className="text-xs text-lvmh-gray">Exemples rapides:</span>
                    {[
                        'Client VIP veut un cadeau pour sa femme, budget 5000€',
                        'Mme Martin cherche un sac à main noir, allergique au cuir véritable',
                        'M. Dubois veut une ceinture marron pour son costume, urgence mariage'
                    ].map((ex, i) => (
                        <button
                            key={i}
                            onClick={() => setInputText(ex)}
                            className="text-xs bg-white/10 hover:bg-white/20 px-3 py-1 rounded-full transition-colors"
                        >
                            {ex.length > 40 ? ex.substring(0, 40) + '...' : ex}
                        </button>
                    ))}
                </div>
            </div>

            {/* Error */}
            {error && (
                <div className="glass border-l-4 border-red-500 p-4 flex items-center gap-3">
                    <AlertCircle className="text-red-500" size={24} />
                    <div>
                        <div className="font-bold text-red-400">Erreur</div>
                        <div className="text-sm text-lvmh-gray">{error}</div>
                    </div>
                </div>
            )}

            {/* Results */}
            {result && (
                <div className="space-y-4">
                    {/* Summary Metrics */}
                    <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                        <MetricCard 
                            label="Tier Utilisé" 
                            value={`T${result.routing?.tier || '?'}`}
                            color={result.routing?.tier === 1 ? 'text-gray-400' : result.routing?.tier === 2 ? 'text-yellow-400' : 'text-red-400'}
                        />
                        <MetricCard 
                            label="Confiance" 
                            value={`${confidencePercent}%`}
                            color={confidencePercent >= 80 ? 'text-green-400' : 'text-yellow-400'}
                        />
                        <MetricCard 
                            label="Temps API" 
                            value={`${result._networkTime}ms`}
                        />
                        <MetricCard 
                            label="Temps Traitement" 
                            value={`${Math.round(result.processing_time_ms || 0)}ms`}
                        />
                        <MetricCard 
                            label="Tags Extraits" 
                            value={allTags.length}
                        />
                        <MetricCard 
                            label="Qualité Score" 
                            value={`${qualityPercent}%`}
                        />
                    </div>

                    {/* Tags */}
                    {allTags.length > 0 && (
                        <div className="glass p-4">
                            <div className="flex items-center gap-2 mb-3">
                                <Tag size={18} className="text-lvmh-gold" />
                                <span className="font-bold">Tags Extraits</span>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                {allTags.map((tag, i) => (
                                    <span 
                                        key={i} 
                                        className="bg-lvmh-gold/20 text-lvmh-gold px-3 py-1 rounded-full text-sm font-medium"
                                    >
                                        {tag}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* 4 Pillars - Pilier 1: Produit */}
                    <Section title="Pilier 1: Univers Produit" icon={ShoppingBag} section="extraction">
                        {result.pilier_1_univers_produit ? (
                            <div className="space-y-3">
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <span className="text-xs text-lvmh-gray">Catégories</span>
                                        <div className="flex flex-wrap gap-1 mt-1">
                                            {(result.pilier_1_univers_produit.categories || []).map((cat, i) => (
                                                <span key={i} className="text-xs bg-white/10 px-2 py-1 rounded">{cat}</span>
                                            ))}
                                        </div>
                                    </div>
                                    <div>
                                        <span className="text-xs text-lvmh-gray">Produits Mentionnés</span>
                                        <div className="flex flex-wrap gap-1 mt-1">
                                            {(result.pilier_1_univers_produit.produits_mentionnes || []).map((p, i) => (
                                                <span key={i} className="text-xs bg-white/10 px-2 py-1 rounded">{p}</span>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                                {result.pilier_1_univers_produit.preferences && (
                                    <div className="bg-white/5 rounded p-3">
                                        <span className="text-xs text-lvmh-gray">Préférences</span>
                                        <div className="grid grid-cols-3 gap-2 mt-2 text-sm">
                                            <div>Couleurs: {(result.pilier_1_univers_produit.preferences.colors || []).join(', ') || '-'}</div>
                                            <div>Matières: {(result.pilier_1_univers_produit.preferences.materials || []).join(', ') || '-'}</div>
                                            <div>Styles: {(result.pilier_1_univers_produit.preferences.styles || []).join(', ') || '-'}</div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="text-lvmh-gray text-sm">Pas de données d'extraction produit</div>
                        )}
                    </Section>

                    {/* Pilier 2: Profil Client */}
                    <Section title="Pilier 2: Profil Client" icon={Users} section="profil">
                        {result.pilier_2_profil_client ? (
                            <div className="space-y-3">
                                <div className="grid grid-cols-3 gap-4">
                                    <div className="bg-white/5 rounded p-3">
                                        <span className="text-xs text-lvmh-gray">Contexte Achat</span>
                                        <div className="text-sm mt-1">
                                            <div>Type: {result.pilier_2_profil_client.purchase_context?.type || '-'}</div>
                                            <div>Comportement: {result.pilier_2_profil_client.purchase_context?.behavior || '-'}</div>
                                            <div>Urgence: {result.pilier_2_profil_client.purchase_context?.urgency || '-'}</div>
                                        </div>
                                    </div>
                                    <div className="bg-white/5 rounded p-3">
                                        <span className="text-xs text-lvmh-gray">Relation</span>
                                        <div className="text-sm mt-1">
                                            <div>Pour: {result.pilier_2_profil_client.relation?.gift_for || '-'}</div>
                                            <div>Occasion: {result.pilier_2_profil_client.relation?.occasion || '-'}</div>
                                        </div>
                                    </div>
                                    <div className="bg-white/5 rounded p-3">
                                        <span className="text-xs text-lvmh-gray">Profil</span>
                                        <div className="text-sm mt-1">
                                            <div>Profession: {result.pilier_2_profil_client.profession?.type || '-'}</div>
                                            <div>Style de vie: {result.pilier_2_profil_client.lifestyle?.type || '-'}</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        ) : (
                            <div className="text-lvmh-gray text-sm">Pas de données de profil client</div>
                        )}
                    </Section>

                    {/* Pilier 3: Hospitalité */}
                    <Section title="Pilier 3: Hospitalité & Care" icon={Shield} section="care">
                        {result.pilier_3_hospitalite_care ? (
                            <div className="space-y-3">
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <span className="text-xs text-lvmh-gray">Allergies / Restrictions</span>
                                        <div className="mt-1">
                                            {(result.pilier_3_hospitalite_care.allergies?.has_allergies) ? (
                                                <span className="text-red-400 text-sm">⚠️ {result.pilier_3_hospitalite_care.allergies.severity}: {(result.pilier_3_hospitalite_care.allergies.items || []).join(', ')}</span>
                                            ) : (
                                                <span className="text-green-400 text-sm">✓ Pas d'allergies détectées</span>
                                            )}
                                        </div>
                                    </div>
                                    <div>
                                        <span className="text-xs text-lvmh-gray">Préférences Livraison</span>
                                        <div className="text-sm mt-1">
                                            {result.pilier_3_hospitalite_care.delivery?.discreet_packaging && (
                                                <span className="text-yellow-400">📦 Emballage discret demandé</span>
                                            )}
                                        </div>
                                    </div>
                                </div>
                                {result.pilier_3_hospitalite_care.occasion && (
                                    <div className="bg-white/5 rounded p-3">
                                        <span className="text-xs text-lvmh-gray">Occasion</span>
                                        <div className="text-sm mt-1">{result.pilier_3_hospitalite_care.occasion}</div>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="text-lvmh-gray text-sm">Pas de données d'hospitalité</div>
                        )}
                    </Section>

                    {/* Pilier 4: Business Action */}
                    <Section title="Pilier 4: Action Business" icon={Lightbulb} section="business">
                        {result.pilier_4_action_business ? (
                            <div className="space-y-3">
                                <div className="grid grid-cols-3 gap-4">
                                    <div className="bg-white/5 rounded p-3">
                                        <span className="text-xs text-lvmh-gray">Budget</span>
                                        <div className="text-lg font-bold text-lvmh-gold mt-1">
                                            {result.pilier_4_action_business.budget_specific
                                                ? `${result.pilier_4_action_business.budget_specific}€`
                                                : (result.pilier_4_action_business.budget_potential || 'Non détecté')}
                                        </div>
                                        {result.pilier_4_action_business.budget_specific && result.pilier_4_action_business.budget_potential && (
                                            <div className="text-sm text-lvmh-gray">
                                                Estimation: {result.pilier_4_action_business.budget_potential}
                                            </div>
                                        )}
                                    </div>
                                    <div className="bg-white/5 rounded p-3">
                                        <span className="text-xs text-lvmh-gray">Urgence</span>
                                        <div className={`text-lg font-bold mt-1 ${
                                            result.pilier_4_action_business.urgency === 'high' ? 'text-red-400' : 
                                            result.pilier_4_action_business.urgency === 'medium' ? 'text-yellow-400' : 'text-green-400'
                                        }`}>
                                            {result.pilier_4_action_business.urgency || 'low'}
                                        </div>
                                    </div>
                                    <div className="bg-white/5 rounded p-3">
                                        <span className="text-xs text-lvmh-gray">Prochaine Action</span>
                                        <div className="text-sm font-medium text-lvmh-gold mt-1">
                                            {formatValue(result.pilier_4_action_business.next_best_action) || 'Aucune'}
                                        </div>
                                        {Array.isArray(result.pilier_4_action_business.next_best_action?.target_products)
                                            && result.pilier_4_action_business.next_best_action.target_products.length > 0 && (
                                            <div className="flex flex-wrap gap-1 mt-2">
                                                {result.pilier_4_action_business.next_best_action.target_products.slice(0, 8).map((product, i) => {
                                                    const label = formatValue(product);
                                                    if (!label) return null;
                                                    return (
                                                        <span key={i} className="text-[10px] bg-white/10 px-2 py-1 rounded">
                                                            {label}
                                                        </span>
                                                    );
                                                })}
                                            </div>
                                        )}
                                    </div>
                                </div>
                                {result.pilier_4_action_business.nba_rationale && (
                                    <div className="bg-lvmh-gold/10 border-l-2 border-lvmh-gold rounded p-3">
                                        <span className="text-xs text-lvmh-gold">💡 Raisonnement NBA</span>
                                        <div className="text-sm mt-1">{result.pilier_4_action_business.nba_rationale}</div>
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="text-lvmh-gray text-sm">Pas de données business</div>
                        )}
                    </Section>

                    {/* RAG - Produits */}
                    <Section title="RAG: Matching Produits" icon={ShoppingBag} section="rag">
                        {result.matched_products && result.matched_products.length > 0 ? (
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                {result.matched_products.map((product, i) => (
                                    <div key={i} className="bg-white/5 rounded-lg p-4 border border-white/10">
                                        <div className="flex justify-between items-start mb-2">
                                            <span className="font-bold">{product.name || product.ID || `Produit ${i + 1}`}</span>
                                            <span className="text-xs bg-lvmh-gold/20 text-lvmh-gold px-2 py-1 rounded">
                                                {Math.round(((product.match_score ?? product.similarity) || 0) * 100)}% match
                                            </span>
                                        </div>
                                        <div className="text-sm text-lvmh-gray">{product.category || 'Categorie N/A'}</div>
                                        <div className="text-lvmh-gold font-bold mt-2">{product.price ? `${product.price}€` : 'Prix N/A'}</div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-lvmh-gray text-sm">Aucun produit matché (RAG non exécuté ou pas de résultats)</div>
                        )}
                    </Section>

                    {/* Routing Details */}
                    <Section title="Routing & Performance" icon={Layers} section="routing">
                        <div className="space-y-3">
                            <div className="grid grid-cols-4 gap-4">
                                <div className="bg-white/5 rounded p-3">
                                    <span className="text-xs text-lvmh-gray">Tier Sélectionné</span>
                                    <div className={`text-2xl font-bold mt-1 ${
                                        result.routing?.tier === 1 ? 'text-gray-400' : 
                                        result.routing?.tier === 2 ? 'text-yellow-400' : 'text-red-400'
                                    }`}>
                                        Tier {result.routing?.tier}
                                    </div>
                                </div>
                                <div className="bg-white/5 rounded p-3">
                                    <span className="text-xs text-lvmh-gray">Confiance Routing</span>
                                    <div className="text-2xl font-bold text-lvmh-gold mt-1">
                                        {Math.round((result.routing?.confidence || 0) * 100)}%
                                    </div>
                                </div>
                                <div className="bg-white/5 rounded p-3">
                                    <span className="text-xs text-lvmh-gray">Priorité</span>
                                    <div className="text-lg font-bold mt-1 capitalize">
                                        {result.routing?.priority || 'normal'}
                                    </div>
                                </div>
                                <div className="bg-white/5 rounded p-3">
                                    <span className="text-xs text-lvmh-gray">Cache Hit</span>
                                    <div className="text-lg font-bold mt-1">
                                        {result.cache_hit ? '✅ Oui' : '❌ Non'}
                                    </div>
                                </div>
                            </div>
                            {result.routing?.reasons && (
                                <div>
                                    <span className="text-xs text-lvmh-gray">Raisons du Routing</span>
                                    <div className="flex flex-wrap gap-2 mt-2">
                                        {result.routing.reasons.map((reason, i) => (
                                            <span key={i} className="text-xs bg-white/10 px-3 py-1 rounded-full">
                                                {reason}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    </Section>

                    {/* RGPD */}
                    <Section 
                        title="RGPD & Anonymisation" 
                        icon={Shield} 
                        section="rgpd"
                        badge={result.rgpd?.contains_sensitive ? { text: 'PII Détecté', color: 'bg-red-500/20 text-red-400' } : { text: 'Clean', color: 'bg-green-500/20 text-green-400' }}
                    >
                        <div className="space-y-3">
                            {result.rgpd?.categories_detected && result.rgpd.categories_detected.length > 0 && (
                                <div>
                                    <span className="text-xs text-lvmh-gray">Catégories PII Détectées</span>
                                    <div className="flex flex-wrap gap-2 mt-2">
                                        {result.rgpd.categories_detected.map((cat, i) => (
                                            <span key={i} className="text-xs bg-red-500/20 text-red-400 px-2 py-1 rounded">
                                                {cat}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                            {result.rgpd?.anonymized_text && (
                                <div className="bg-white/5 rounded p-3">
                                    <span className="text-xs text-lvmh-gray">Texte Anonymisé</span>
                                    <div className="text-sm mt-1 font-mono text-lvmh-gold">
                                        {result.rgpd.anonymized_text}
                                    </div>
                                </div>
                            )}
                        </div>
                    </Section>

                    {/* Meta Analysis */}
                    <Section title="Méta-Analyse & Qualité" icon={Brain} section="meta">
                        <div className="space-y-3">
                            {result.meta_analysis && (
                                <div className="grid grid-cols-3 gap-4">
                                    <div className="bg-white/5 rounded p-3">
                                        <span className="text-xs text-lvmh-gray">Quality Score</span>
                                        <div className="text-2xl font-bold text-lvmh-gold mt-1">
                                            {qualityPercent}%
                                        </div>
                                    </div>
                                    <div className="bg-white/5 rounded p-3">
                                        <span className="text-xs text-lvmh-gray">Confiance Extraction</span>
                                        <div className="text-2xl font-bold text-lvmh-gold mt-1">
                                            {confidencePercent}%
                                        </div>
                                    </div>
                                    <div className="bg-white/5 rounded p-3">
                                        <span className="text-xs text-lvmh-gray">Complétude</span>
                                        <div className="text-2xl font-bold text-lvmh-gold mt-1">
                                            {completenessPercent}%
                                        </div>
                                    </div>
                                </div>
                            )}
                            {result.meta_analysis?.missing_info && result.meta_analysis.missing_info.length > 0 && (
                                <div className="bg-yellow-500/10 border-l-2 border-yellow-500 rounded p-3">
                                    <span className="text-xs text-yellow-400">⚠️ Informations Manquantes</span>
                                    <div className="text-sm mt-1">{result.meta_analysis.missing_info.join(', ')}</div>
                                </div>
                            )}
                            {result.meta_analysis?.risk_flags && result.meta_analysis.risk_flags.length > 0 && (
                                <div className="bg-red-500/10 border-l-2 border-red-500 rounded p-3">
                                    <span className="text-xs text-red-400">🚩 Risk Flags</span>
                                    <div className="text-sm mt-1">{result.meta_analysis.risk_flags.join(', ')}</div>
                                </div>
                            )}
                        </div>
                    </Section>

                    {/* Raw JSON (Collapsible) */}
                    <div className="glass overflow-hidden">
                        <button
                            onClick={() => toggleSection('raw')}
                            className="w-full flex items-center justify-between p-4 hover:bg-white/5 transition-colors text-lvmh-gray"
                        >
                            <span className="text-xs uppercase">JSON Brut (Debug Avancé)</span>
                            {expandedSections.raw ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                        </button>
                        {expandedSections.raw && (
                            <div className="px-4 pb-4">
                                <pre className="bg-black/50 rounded p-4 text-xs overflow-auto max-h-96 font-mono">
                                    {JSON.stringify(result, null, 2)}
                                </pre>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}
