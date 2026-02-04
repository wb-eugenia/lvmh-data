import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { User, Lock, ArrowRight, AlertCircle } from 'lucide-react';

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
        <div className="min-h-screen bg-[#0D1A2D] text-white flex items-center justify-center p-6">
            {/* LVMH Pattern Background */}
            <div className="lvmh-pattern" />

            <div className="w-full max-w-sm relative z-10 fade-in">
                {/* Logo */}
                <div className="text-center mb-12">
                    <div className="text-4xl font-light tracking-tight mb-2">LVMH</div>
                    <div className="text-subtitle">CLIENTELING ASSISTANT</div>
                </div>

                {/* Login Card */}
                <div className="card p-8">
                    <form onSubmit={handleSubmit} className="space-y-5">
                        {/* Email */}
                        <div>
                            <label className="text-subtitle block mb-2">IDENTIFIANT</label>
                            <div className="relative">
                                <User className="absolute left-4 top-1/2 -translate-y-1/2 text-[#718096]" size={18} />
                                <input
                                    type="text"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    placeholder="advisor@lvmh.com"
                                    className="input pl-12"
                                />
                            </div>
                        </div>

                        {/* Password */}
                        <div>
                            <label className="text-subtitle block mb-2">MOT DE PASSE</label>
                            <div className="relative">
                                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 text-[#718096]" size={18} />
                                <input
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    placeholder="••••••••"
                                    className="input pl-12"
                                />
                            </div>
                        </div>

                        {/* Error */}
                        {error && (
                            <div className="flex items-center gap-2 text-red-400 text-sm bg-red-500/10 border border-red-500/20 p-3 rounded-lg fade-in">
                                <AlertCircle size={16} />
                                <span>{error}</span>
                            </div>
                        )}

                        {/* Submit */}
                        <button
                            type="submit"
                            disabled={isLoading}
                            className="btn-primary w-full flex justify-center items-center gap-2"
                        >
                            {isLoading ? (
                                <div className="spinner" />
                            ) : (
                                <>
                                    Connexion
                                    <ArrowRight size={18} />
                                </>
                            )}
                        </button>
                    </form>
                </div>

                {/* Demo credentials */}
                <div className="mt-8 text-center">
                    <p className="text-caption mb-2">Comptes de démonstration</p>
                    <div className="card inline-block px-4 py-3">
                        <p className="text-caption"><span className="text-white">advisor@lvmh.com</span> / lvmh</p>
                        <p className="text-caption"><span className="text-white">manager@lvmh.com</span> / lvmh</p>
                    </div>
                </div>
            </div>
        </div>
    );
}
