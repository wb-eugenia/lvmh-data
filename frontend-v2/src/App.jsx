import React, { useState, useEffect } from 'react'
import LandingPage from './components/LandingPage'
import AdvisorView from './components/AdvisorView'
import ManagerView from './components/ManagerView'
import LoginView from './components/LoginView'
import { AuthProvider, useAuth } from './context/AuthContext'

function AppContent() {
    // Determine view from URL or state
    const [view, setView] = useState('landing')
    const { user, loading } = useAuth()

    useEffect(() => {
        // Simple URL routing simulation
        const path = window.location.pathname
        if (path === '/login') setView('login')
        else if (path === '/advisor') setView('advisor')
        else if (path === '/manager') setView('manager')
    }, [])

    const navigate = (newView) => {
        setView(newView)
        // Optional: Update URL without reload
        window.history.pushState({}, '', newView === 'landing' ? '/' : `/${newView}`)
    }

    if (loading) return <div className="h-screen bg-black text-white flex items-center justify-center">Chargement...</div>

    // Protected Routes
    if (view === 'advisor' && !user) return <LoginView />
    if (view === 'manager' && !user) return <LoginView />
    if (view === 'login') return <LoginView />

    // Role Enforcement (Optional: redirect advisor trying to access manager view)
    if (view === 'manager' && user?.role !== 'manager') {
        return <div className="h-screen flex items-center justify-center text-white">Accès Réservé au Manager</div>
    }

    return (
        <div className="min-h-screen">
            {view === 'landing' && <LandingPage onNavigate={navigate} />}
            {view === 'advisor' && <AdvisorView onBack={() => navigate('landing')} />}
            {view === 'manager' && <ManagerView onBack={() => navigate('landing')} />}
            {view === 'login' && <LoginView />}
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
