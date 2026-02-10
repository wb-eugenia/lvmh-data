import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { User, Lock, Sparkles, AlertCircle } from 'lucide-react';

export default function LoginView() {
    const { login } = useAuth();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [isLoading, setIsLoading] = useState(false);

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
        <div className="min-h-screen bg-lvmh-black text-white flex items-center justify-center p-4">
            <div className="absolute inset-0 bg-[url('https://images.unsplash.com/photo-1549488344-c7052fb51f22?q=80&w=2670&auto=format&fit=crop')] bg-cover opacity-20 pointer-events-none"></div>

            <div className="w-full max-w-md glass p-10 relative z-10 animate-in fade-in zoom-in duration-500">
                <div className="text-center mb-10">
                    <h1 className="text-4xl font-display mb-2">LVMH</h1>
                    <p className="text-lvmh-gold uppercase tracking-widest text-xs">Excellence Retail & Clienteling</p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-6">
                    <div>
                        <label className="block text-xs uppercase tracking-widest text-lvmh-gray mb-2">Identifiant LVMH</label>
                        <div className="relative">
                            <User className="absolute left-4 top-3.5 text-lvmh-gold/50" size={18} />
                            <input
                                type="text"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                placeholder="advisor@lvmh.com"
                                className="w-full bg-white/5 border border-white/10 rounded-sm py-3 pl-12 pr-4 text-white placeholder-white/20 focus:outline-none focus:border-lvmh-gold transition-colors"
                            />
                        </div>
                    </div>

                    <div>
                        <label className="block text-xs uppercase tracking-widest text-lvmh-gray mb-2">Mot de Passe</label>
                        <div className="relative">
                            <Lock className="absolute left-4 top-3.5 text-lvmh-gold/50" size={18} />
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                placeholder="••••••••"
                                className="w-full bg-white/5 border border-white/10 rounded-sm py-3 pl-12 pr-4 text-white placeholder-white/20 focus:outline-none focus:border-lvmh-gold transition-colors"
                            />
                        </div>
                    </div>

                    {error && (
                        <div className="flex items-center gap-2 text-red-400 text-sm bg-red-400/10 p-3 rounded">
                            <AlertCircle size={16} /> {error}
                        </div>
                    )}

                    <button
                        type="submit"
                        disabled={isLoading}
                        className="w-full bg-lvmh-gold text-black font-bold py-4 uppercase tracking-widest hover:bg-white transition-all disabled:opacity-50 disabled:cursor-not-allowed flex justify-center items-center gap-2"
                    >
                        {isLoading ? (
                            <div className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin"></div>
                        ) : (
                            <>
                                <Sparkles size={18} /> Connexion
                            </>
                        )}
                    </button>

                    <div className="text-center text-xs text-lvmh-gray mt-4">
                        <p>Demo Credentials:</p>
                        <p>Advisor: advisor@lvmh.com / lvmh</p>
                        <p>Manager: manager@lvmh.com / lvmh</p>
                    </div>
                </form>
            </div>
        </div>
    );
}
