import React, { useState } from 'react'
import LandingPage from './components/LandingPage'
import AdvisorView from './components/AdvisorView'
import ManagerView from './components/ManagerView'

function App() {
    const [view, setView] = useState('landing') // 'landing', 'advisor', 'manager'

    return (
        <div className="min-h-screen">
            {view === 'landing' && <LandingPage onNavigate={setView} />}
            {view === 'advisor' && <AdvisorView onBack={() => setView('landing')} />}
            {view === 'manager' && <ManagerView onBack={() => setView('landing')} />}
        </div>
    )
}

export default App
