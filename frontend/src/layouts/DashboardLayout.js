import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { FalconLogo } from '../components/FalconLogo';
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuSeparator,
    DropdownMenuTrigger,
} from '../components/ui/dropdown-menu';
import {
    LayoutDashboard,
    Bell,
    AlertTriangle,
    BookOpen,
    BarChart3,
    Settings,
    User,
    LogOut,
    Menu,
    X,
    Activity,
    Hexagon,
    FileText,
    Network,
    GitBranch,
    Cpu,
    Server,
    Shield,
    ScrollText,
    Download,
    Brain,
    Sparkles,
} from 'lucide-react';

const navItems = [
    { path: '/dashboard', label: 'COMMAND', icon: LayoutDashboard },
    { path: '/intelligence', label: 'INTELLIGENCE', icon: Sparkles },
    { path: '/monitoring', label: 'MONITORING', icon: Activity },
    { path: '/servers', label: 'SERVERS', icon: Server },
    { path: '/logs', label: 'LOGS', icon: ScrollText },
    { path: '/event-analyzer', label: 'AI ANALYZER', icon: Brain },
    { path: '/apm', label: 'APM', icon: Cpu },
    { path: '/honeycomb', label: 'SERVICES', icon: Hexagon },
    { path: '/topology', label: 'TOPOLOGY', icon: GitBranch },
    { path: '/alerts', label: 'ALERTS', icon: Bell },
    { path: '/incidents', label: 'INCIDENTS', icon: AlertTriangle },
    { path: '/runbooks', label: 'AUTOMATION', icon: BookOpen },
    { path: '/analytics', label: 'ANALYTICS', icon: BarChart3 },
    { path: '/reports', label: 'REPORTS', icon: FileText },
    { path: '/settings', label: 'SETTINGS', icon: Settings },
    { path: '/admin', label: 'ADMIN', icon: Shield, adminOnly: true },
    { path: '/download', label: 'DOWNLOAD', icon: Download, adminOnly: true },
];

export const DashboardLayout = ({ children }) => {
    const { user, logout } = useAuth();
    const location = useLocation();
    const [mobileMenuOpen, setMobileMenuOpen] = React.useState(false);

    return (
        <div className="min-h-screen bg-[#0B0F14]">
            {/* Subtle scanline effect */}
            <div className="scanline" />
            
            {/* Top Navigation */}
            <header className="sticky top-0 z-50 bg-[#0B0F14]/90 backdrop-blur-xl border-b border-white/5">
                <div className="flex h-14 items-center justify-between px-4 lg:px-6">
                    {/* Logo - FalconOps AI */}
                    <Link to="/dashboard" className="flex items-center gap-3">
                        <FalconLogo size={36} />
                        <span className="font-heading font-semibold text-lg tracking-wide hidden sm:flex items-baseline gap-0.5">
                            <span className="text-[#F5B841]">FALCON</span>
                            <span className="text-white">OPS</span>
                            <span className="text-[#00E0FF] text-sm ml-1">AI</span>
                        </span>
                    </Link>

                    {/* Desktop Nav */}
                    <nav className="hidden lg:flex items-center gap-1">
                        {navItems.filter(item => !item.adminOnly || user?.role === 'admin').map((item) => {
                            const Icon = item.icon;
                            const isActive = location.pathname === item.path;
                            return (
                                <Link
                                    key={item.path}
                                    to={item.path}
                                    data-testid={`nav-${item.label.toLowerCase()}`}
                                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold tracking-wide transition-all duration-200 ${
                                        isActive
                                            ? item.adminOnly 
                                                ? 'bg-red-500/10 text-red-400 border border-red-500/30'
                                                : 'bg-[#F5B841]/10 text-[#F5B841] border border-[#F5B841]/30'
                                            : 'text-white/50 hover:text-white hover:bg-white/5 border border-transparent'
                                    }`}
                                >
                                    <Icon className="w-4 h-4" />
                                    {item.label}
                                </Link>
                            );
                        })}
                    </nav>

                    {/* User Menu */}
                    <div className="flex items-center gap-3">
                        {/* Live indicator with pulse animation */}
                        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-[#00C853]/10 border border-[#00C853]/20 rounded-lg">
                            <div className="live-dot" />
                            <span className="text-[10px] text-[#00C853] font-mono uppercase tracking-wider">Live</span>
                        </div>
                        
                        <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                                <Button
                                    variant="ghost"
                                    data-testid="user-menu-trigger"
                                    className="flex items-center gap-2 hover:bg-white/5 rounded-sm"
                                >
                                    <div className="w-8 h-8 rounded-sm bg-primary/20 border border-primary/30 flex items-center justify-center">
                                        <User className="w-4 h-4 text-primary" />
                                    </div>
                                    <span className="hidden sm:block text-xs font-bold text-white/70 uppercase tracking-wider">
                                        {user?.full_name?.split(' ')[0] || 'User'}
                                    </span>
                                </Button>
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end" className="w-56 bg-[#0a0a0a] border-white/10 rounded-sm">
                                <div className="px-3 py-3 border-b border-white/10">
                                    <p className="text-sm font-bold text-white">{user?.full_name}</p>
                                    <p className="text-xs text-white/50 font-mono">{user?.email}</p>
                                </div>
                                <DropdownMenuItem asChild>
                                    <Link to="/settings" className="flex items-center gap-2 cursor-pointer text-white/70 hover:text-white">
                                        <Settings className="w-4 h-4" />
                                        Settings
                                    </Link>
                                </DropdownMenuItem>
                                <DropdownMenuSeparator className="bg-white/10" />
                                <DropdownMenuItem
                                    onClick={logout}
                                    data-testid="logout-btn"
                                    className="text-red-400 hover:text-red-300 cursor-pointer"
                                >
                                    <LogOut className="w-4 h-4 mr-2" />
                                    Logout
                                </DropdownMenuItem>
                            </DropdownMenuContent>
                        </DropdownMenu>

                        {/* Mobile Menu Toggle */}
                        <Button
                            variant="ghost"
                            size="icon"
                            className="lg:hidden hover:bg-white/5 rounded-sm"
                            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                            data-testid="mobile-menu-toggle"
                        >
                            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
                        </Button>
                    </div>
                </div>

                {/* Mobile Nav */}
                {mobileMenuOpen && (
                    <nav className="lg:hidden border-t border-white/5 p-3 space-y-1 bg-black/90 animate-fade-in">
                        {navItems.filter(item => !item.adminOnly || user?.role === 'admin').map((item) => {
                            const Icon = item.icon;
                            const isActive = location.pathname === item.path;
                            return (
                                <Link
                                    key={item.path}
                                    to={item.path}
                                    onClick={() => setMobileMenuOpen(false)}
                                    className={`flex items-center gap-3 px-4 py-3 rounded-sm text-xs font-bold tracking-wider ${
                                        isActive
                                            ? item.adminOnly 
                                                ? 'bg-red-500/10 text-red-400 border border-red-500/30'
                                                : 'bg-primary/10 text-primary border border-primary/30'
                                            : 'text-white/50 hover:text-white hover:bg-white/5'
                                    }`}
                                >
                                    <Icon className="w-5 h-5" />
                                    {item.label}
                                </Link>
                            );
                        })}
                    </nav>
                )}
            </header>

            {/* Main Content */}
            <main className="p-4 lg:p-6">{children}</main>
        </div>
    );
};
