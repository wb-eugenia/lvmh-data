import React, { lazy, Suspense, useState, useEffect } from 'react'
import LandingPage from './components/LandingPage'
import LoginView from './components/LoginView'
import { AuthProvider, useAuth } from './context/AuthContext'

const AdvisorView = lazy(() => import('./components/AdvisorView'))
const ManagerView = lazy(() => import('./components/ManagerView'))
const AdminView = lazy(() => import('./components/AdminPanel'))
const PipelineView = lazy(() => import('./components/PipelineView'))
const ProductsView = lazy(() => import('./components/ProductsView'))

const viewByPath = (path) => {
    const normalizedPath = (path || '/').replace(/\/+$/, '') || '/'
    if (normalizedPath === '/login') return 'login'
    if (normalizedPath === '/advisor') return 'advisor'
    if (normalizedPath === '/manager') return 'manager'
    if (normalizedPath === '/admin') return 'admin'
    if (normalizedPath === '/pipeline') return 'pipeline'
    if (normalizedPath === '/products') return 'products'
    return 'landing'
}

const pathByView = (view) => {
    if (view === 'login') return '/login'
    if (view === 'advisor') return '/advisor'
    if (view === 'manager') return '/manager'
    if (view === 'admin') return '/admin'
    if (view === 'pipeline') return '/pipeline'
    if (view === 'products') return '/products'
    return '/'
}

function AppContent() {
    // Determine view from URL or state
    const [view, setView] = useState('landing')
    const { user, loading } = useAuth()

    useEffect(() => {
        const syncViewFromUrl = () => setView(viewByPath(window.location.pathname))
        syncViewFromUrl()
        window.addEventListener('popstate', syncViewFromUrl)
        return () => window.removeEventListener('popstate', syncViewFromUrl)
    }, [])

    const navigate = (newView) => {
        setView(newView)
        window.history.pushState({}, '', pathByView(newView))
    }

    if (loading) return <div className="h-screen bg-black text-white flex items-center justify-center">Chargement...</div>

    // Protected Routes
    if (view === 'advisor' && !user) return <LoginView />
    if (view === 'manager' && !user) return <LoginView />
    if (view === 'admin' && !user) return <LoginView />
    if (view === 'login') return <LoginView />
    if (view === 'admin' && user?.role !== 'admin') {
        return (
            <div className="h-screen bg-black text-white flex items-center justify-center p-6">
                <div className="glass p-8 max-w-md text-center">
                    <div className="text-silver text-sm uppercase tracking-widest mb-3">Acces restreint</div>
                    <h2 className="text-2xl font-display font-bold mb-2">Admin Total</h2>
                    <p className="text-lvmh-gray text-sm">Cette vue est reservee au role admin.</p>
                    <button
                        onClick={() => navigate('landing')}
                        className="mt-6 px-5 py-2 rounded-lg bg-silver text-black font-bold text-sm hover:bg-silver/90 transition-colors"
                    >
                        Retour
                    </button>
                </div>
            </div>
        )
    }

    return (
        <div className="min-h-screen">
            <Suspense fallback={<div className="h-screen bg-black text-white flex items-center justify-center">Chargement...</div>}>
                {view === 'landing' && <LandingPage onNavigate={navigate} />}
                {view === 'advisor' && <AdvisorView onBack={() => navigate('landing')} />}
                {view === 'manager' && <ManagerView onBack={() => navigate('landing')} />}
                {view === 'admin' && <AdminView onBack={() => navigate('landing')} />}
                {view === 'pipeline' && <PipelineView onBack={() => navigate('landing')} />}
                {view === 'products' && <ProductsView onBack={() => navigate('landing')} />}
                {view === 'login' && <LoginView />}
            </Suspense>
        </div>
    )
}

function App() {
    return (
        <AuthProvider>
            <AppContent />
        </AuthProvider>
    )
}

export default App


