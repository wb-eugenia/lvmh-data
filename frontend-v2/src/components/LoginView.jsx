import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { User, Lock, Sparkles, AlertCircle } from 'lucide-react';

function SilverParticles() {
    const particles = Array.from({ length: 15 }, (_, i) => ({
        id: i,
        left: `${Math.random() * 100}%`,
        delay: `${Math.random() * 15}s`,
        duration: `${15 + Math.random() * 10}s`,
        size: `${2 + Math.random() * 3}px`,
    }))

    return (
        <div className="gold-particles">
            {particles.map(p => (
                <div
                    key={p.id}
                    className="gold-particle"
                    style={{
                        left: p.left,
                        animationDelay: p.delay,
                        animationDuration: p.duration,
                        width: p.size,
                        height: p.size,
                    }}
                />
            ))}
        </div>
    )
}

export default function LoginView() {
    const { login, user } = useAuth();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);

    React.useEffect(() => {
        if (user) {
            const targetPath = user.role === 'manager' ? '/manager' : '/advisor';
            window.location.href = targetPath;
        }
    }, [user]);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setIsLoading(true);
        setError('');

        if (!email || !password) {
            setError('Veuillez remplir tous les champs');
            setIsLoading(false);
            return;
        }

        const success = await login(email, password);
        if (!success) {
            setError('Identifiants incorrects');
        }
        setIsLoading(false);
    };

    return (
        <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden">
            <SilverParticles />
            
            <div className="absolute inset-0 bg-[url('https://images.unsplash.com/photo-1549488344-c7052fb51f22?q=80&w=2670&auto=format&fit=crop')] bg-cover opacity-10 pointer-events-none"></div>

            <div className="w-full max-w-md glass-card p-10 relative z-10">
                <div className="text-center mb-10">
                    <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-[#C0C0C0] to-[#A0A0A0] flex items-center justify-center shadow-xl shadow-silver/30">
                        <Sparkles className="text-[#0C1929] w-8 h-8" />
                    </div>
                    <h1 className="text-4xl font-display font-bold gold-text mb-2">LVMH</h1>
                    <p className="text-lvmh-gray uppercase tracking-[0.25em] text-xs">Excellence Retail & Clienteling</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-5">
                    <div className="space-y-2">
                        <label className="block text-xs uppercase tracking-widest text-lvmh-gray font-medium">Identifiant LVMH</label>
                        <div className="flex items-center gap-3 bg-white/5 border border-white/10 rounded-xl px-4 py-3">
                            <User className="text-silver/60 shrink-0" size={20} />
                            <input
                                type="text"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                placeholder="votre@email.com"
                                className="bg-transparent border-none outline-none text-white placeholder-white/40 w-full text-base"
                            />
                        </div>
                    </div>

                    <div className="space-y-2">
                        <label className="block text-xs uppercase tracking-widest text-lvmh-gray font-medium">Mot de Passe</label>
                        <div className="flex items-center gap-3 bg-white/5 border border-white/10 rounded-xl px-4 py-3">
                            <Lock className="text-silver/60 shrink-0" size={20} />
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="••••••••"
                                className="bg-transparent border-none outline-none text-white placeholder-white/40 w-full text-base"
                            />
                        </div>
                    </div>

                    {error && (
                        <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 p-3 rounded-lg border border-red-400/20">
                            <AlertCircle size={16} /> {error}
                        </div>
                    )}

                    <button
                        type="submit"
                        disabled={isLoading}
                        className="btn-gold w-full py-4 uppercase tracking-widest flex justify-center items-center gap-2 text-base mt-4"
                    >
                        {isLoading ? (
                            <div className="spinner-gold"></div>
                        ) : (
                            <>
                                <Sparkles size={18} /> Connexion
                            </>
                        )}
                    </button>
                </form>
            </div>
        </div>
    );
}
