import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { toast } from 'sonner';
import { Eye, EyeOff, ArrowRight, Loader2, X } from 'lucide-react';
import { motion } from 'framer-motion';

export const LoginPage = () => {
    const { login } = useAuth();
    const navigate = useNavigate();
    const [loading, setLoading] = useState(false);
    const [showPassword, setShowPassword] = useState(false);
    const [formData, setFormData] = useState({
        email: '',
        password: '',
    });

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            await login(formData.email, formData.password);
            toast.success('Welcome back!');
            navigate('/dashboard');
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Login failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center px-4 py-12 bg-[#050505]">
            {/* Background elements */}
            <div className="absolute inset-0 obsidian-grid opacity-30" />
            <div 
                className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[400px] rounded-full blur-3xl"
                style={{ background: 'radial-gradient(circle, rgba(212, 175, 55, 0.1) 0%, transparent 70%)' }}
            />
            
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
            >
                <Card className="relative w-full max-w-md bg-black/60 backdrop-blur-xl border-white/10 rounded-sm">
                    {/* Close button → back to landing */}
                    <Link
                        to="/"
                        data-testid="login-close-btn"
                        aria-label="Close and return to home"
                        className="absolute top-3 right-3 z-10 w-8 h-8 rounded-full bg-white/5 hover:bg-white/15 border border-white/10 flex items-center justify-center text-white/60 hover:text-white transition-colors"
                    >
                        <X className="w-4 h-4" />
                    </Link>
                    <CardHeader className="text-center pb-4">
                        <Link to="/" className="flex items-center justify-center gap-2 mb-6">
                            <div className="w-12 h-12 rounded-sm bg-primary/20 border border-primary/30 flex items-center justify-center">
                                <span className="text-primary font-heading font-bold text-2xl">F</span>
                            </div>
                        </Link>
                        <CardTitle className="font-heading font-bold text-2xl uppercase tracking-wider text-white">Welcome Back</CardTitle>
                        <CardDescription className="text-white/50 font-mono text-sm">Sign in to your FalconOps AI account</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <form onSubmit={handleSubmit} className="space-y-5">
                            <div className="space-y-2">
                                <Label htmlFor="email" className="text-white/70 text-xs uppercase tracking-wider font-mono">Email</Label>
                                <Input
                                    id="email"
                                    type="email"
                                    placeholder="you@company.com"
                                    data-testid="login-email"
                                    value={formData.email}
                                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                    required
                                    className="bg-black/50 border-white/10 focus:border-primary/50 rounded-sm text-white placeholder:text-white/30 h-11"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="password" className="text-white/70 text-xs uppercase tracking-wider font-mono">Password</Label>
                                <div className="relative">
                                    <Input
                                        id="password"
                                        type={showPassword ? 'text' : 'password'}
                                        placeholder="••••••••"
                                        data-testid="login-password"
                                        value={formData.password}
                                        onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                                        required
                                        className="bg-black/50 border-white/10 focus:border-primary/50 rounded-sm text-white placeholder:text-white/30 h-11 pr-10"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowPassword(!showPassword)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/70"
                                    >
                                        {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                    </button>
                                </div>
                            </div>
                            <Button 
                                type="submit" 
                                className="w-full bg-primary text-black hover:bg-primary/90 font-bold uppercase tracking-wider rounded-sm h-11 glow-primary" 
                                disabled={loading}
                                data-testid="login-submit"
                            >
                                {loading ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                ) : (
                                    <>
                                        Sign In
                                        <ArrowRight className="w-4 h-4 ml-2" />
                                    </>
                                )}
                            </Button>
                        </form>
                        <div className="mt-6 text-center text-sm text-white/40">
                            Don't have an account?{' '}
                            <Link to="/register" className="text-primary hover:text-primary/80 font-medium" data-testid="register-link">
                                Sign up
                            </Link>
                        </div>
                    </CardContent>
                </Card>
            </motion.div>
        </div>
    );
};

export const RegisterPage = () => {
    const { register } = useAuth();
    const navigate = useNavigate();
    const [loading, setLoading] = useState(false);
    const [showPassword, setShowPassword] = useState(false);

    // Read ?plan=X from the URL so onboarding stays in context
    const planFromQuery = (() => {
        try { return new URLSearchParams(window.location.search).get('plan') || ''; }
        catch { return ''; }
    })();

    const [formData, setFormData] = useState({
        email: '',
        password: '',
        full_name: '',
        organization: '',
    });

    const handleSubmit = async (e) => {
        e.preventDefault();
        setLoading(true);
        try {
            await register(formData.email, formData.password, formData.full_name, formData.organization);
            toast.success('Account created successfully!');
            // Route based on the plan the user originally clicked on the pricing page
            const plan = (planFromQuery || '').toLowerCase();
            if (plan && plan !== 'trial' && plan !== 'free') {
                // Paid plan → drop user into the billing page with the plan pre-selected
                navigate(`/billing?plan=${encodeURIComponent(plan)}`);
            } else {
                navigate('/dashboard');
            }
        } catch (error) {
            toast.error(error.response?.data?.detail || 'Registration failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center px-4 py-12 bg-[#050505]">
            {/* Background elements */}
            <div className="absolute inset-0 obsidian-grid opacity-30" />
            <div 
                className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[400px] rounded-full blur-3xl"
                style={{ background: 'radial-gradient(circle, rgba(0, 240, 255, 0.08) 0%, transparent 70%)' }}
            />
            
            <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.4 }}
            >
                <Card className="relative w-full max-w-md bg-black/60 backdrop-blur-xl border-white/10 rounded-sm">
                    {/* Close button → back to landing */}
                    <Link
                        to="/"
                        data-testid="register-close-btn"
                        aria-label="Close and return to home"
                        className="absolute top-3 right-3 z-10 w-8 h-8 rounded-full bg-white/5 hover:bg-white/15 border border-white/10 flex items-center justify-center text-white/60 hover:text-white transition-colors"
                    >
                        <X className="w-4 h-4" />
                    </Link>
                    <CardHeader className="text-center pb-4">
                        <Link to="/" className="flex items-center justify-center gap-2 mb-6">
                            <div className="w-12 h-12 rounded-sm bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center">
                                <span className="text-cyan-400 font-heading font-bold text-2xl">F</span>
                            </div>
                        </Link>
                        <CardTitle className="font-heading font-bold text-2xl uppercase tracking-wider text-white">Create Account</CardTitle>
                        <CardDescription className="text-white/50 font-mono text-sm">Start your 14-day free trial</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <form onSubmit={handleSubmit} className="space-y-4">
                            <div className="space-y-2">
                                <Label htmlFor="full_name" className="text-white/70 text-xs uppercase tracking-wider font-mono">Full Name</Label>
                                <Input
                                    id="full_name"
                                    type="text"
                                    placeholder="Ahmed Al-Rashid"
                                    data-testid="register-name"
                                    value={formData.full_name}
                                    onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                                    required
                                    className="bg-black/50 border-white/10 focus:border-cyan-500/50 rounded-sm text-white placeholder:text-white/30 h-11"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="organization" className="text-white/70 text-xs uppercase tracking-wider font-mono">Organization (Optional)</Label>
                                <Input
                                    id="organization"
                                    type="text"
                                    placeholder="Saudi Telecom"
                                    data-testid="register-org"
                                    value={formData.organization}
                                    onChange={(e) => setFormData({ ...formData, organization: e.target.value })}
                                    className="bg-black/50 border-white/10 focus:border-cyan-500/50 rounded-sm text-white placeholder:text-white/30 h-11"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="email" className="text-white/70 text-xs uppercase tracking-wider font-mono">Email</Label>
                                <Input
                                    id="email"
                                    type="email"
                                    placeholder="you@company.com"
                                    data-testid="register-email"
                                    value={formData.email}
                                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                                    required
                                    className="bg-black/50 border-white/10 focus:border-cyan-500/50 rounded-sm text-white placeholder:text-white/30 h-11"
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="password" className="text-white/70 text-xs uppercase tracking-wider font-mono">Password</Label>
                                <div className="relative">
                                    <Input
                                        id="password"
                                        type={showPassword ? 'text' : 'password'}
                                        placeholder="••••••••"
                                        data-testid="register-password"
                                        value={formData.password}
                                        onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                                        required
                                        minLength={6}
                                        className="bg-black/50 border-white/10 focus:border-cyan-500/50 rounded-sm text-white placeholder:text-white/30 h-11 pr-10"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => setShowPassword(!showPassword)}
                                        className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/70"
                                    >
                                        {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                    </button>
                                </div>
                            </div>
                            <Button 
                                type="submit" 
                                className="w-full bg-cyan-500 text-black hover:bg-cyan-400 font-bold uppercase tracking-wider rounded-sm h-11 glow-cyan" 
                                disabled={loading}
                                data-testid="register-submit"
                            >
                                {loading ? (
                                    <Loader2 className="w-4 h-4 animate-spin" />
                                ) : (
                                    <>
                                        Create Account
                                        <ArrowRight className="w-4 h-4 ml-2" />
                                    </>
                                )}
                            </Button>
                        </form>
                        <div className="mt-6 text-center text-sm text-white/40">
                            Already have an account?{' '}
                            <Link to="/login" className="text-cyan-400 hover:text-cyan-300 font-medium" data-testid="login-link">
                                Sign in
                            </Link>
                        </div>
                    </CardContent>
                </Card>
            </motion.div>
        </div>
    );
};
