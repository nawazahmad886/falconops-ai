import React, { useState, useEffect, useRef } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { ScrollArea } from '../components/ui/scroll-area';
import { toast } from 'sonner';
import {
    Bot, Send, Plus, Trash2, Check, X, Loader2, ShieldCheck,
    Sparkles, MessageSquare, Activity, Clock, AlertCircle,
    CheckCircle2, XCircle, Zap, User, RefreshCw,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL;
const authHeaders = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${localStorage.getItem('falconToken')}`,
});

const ACTION_LABELS = {
    create_url_monitor: 'Create URL Monitor',
    toggle_monitor: 'Toggle Monitor',
    delete_monitor: 'Delete Monitor',
    update_monitor: 'Update Monitor',
    run_check_now: 'Run Check Now',
};

const STATUS_COLORS = {
    pending: 'bg-amber-500/15 text-amber-400 border-amber-500/30',
    approved: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/30',
    rejected: 'bg-zinc-500/15 text-zinc-400 border-zinc-500/30',
    executed: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
    failed: 'bg-red-500/15 text-red-400 border-red-500/30',
};

// ───────────── Action Approval Card ─────────────

const ActionCard = ({ action, onApprove, onReject, isAdmin, busy }) => {
    const [expanded, setExpanded] = useState(true);
    const params = action.params || {};
    const execResult = action.execution_result || {};

    return (
        <div className={`mt-2 p-4 rounded-lg border bg-black/40 ${
            action.status === 'pending' ? 'border-amber-500/40' : 'border-white/10'
        }`} data-testid={`action-card-${action.id}`}>
            <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-2.5 min-w-0 flex-1">
                    <div className="p-1.5 rounded bg-[#F5B841]/10 shrink-0">
                        <Sparkles className="w-4 h-4 text-[#F5B841]" />
                    </div>
                    <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                            <span className="text-sm font-semibold text-white">
                                {ACTION_LABELS[action.action] || action.action}
                            </span>
                            <Badge className={`text-[10px] border ${STATUS_COLORS[action.status] || ''}`}>
                                {action.status}
                            </Badge>
                        </div>
                        {action.summary && (
                            <p className="text-xs text-white/60 mb-2 leading-relaxed">{action.summary}</p>
                        )}
                    </div>
                </div>
                <button
                    onClick={() => setExpanded(!expanded)}
                    className="text-[10px] text-white/40 hover:text-white/70 shrink-0"
                    data-testid={`toggle-action-${action.id}`}
                >
                    {expanded ? 'Hide' : 'Show'} details
                </button>
            </div>

            {expanded && (
                <div className="mt-3 space-y-2">
                    <div className="p-2.5 bg-black/60 rounded border border-white/5">
                        <div className="text-[10px] uppercase tracking-widest text-white/40 mb-1.5">Proposed Config</div>
                        <pre className="text-[11px] text-white/70 font-mono overflow-x-auto whitespace-pre-wrap break-all">
                            {JSON.stringify(params, null, 2)}
                        </pre>
                    </div>

                    {action.status === 'executed' && execResult.created_monitor && (
                        <div className="p-2 bg-emerald-500/[0.06] border border-emerald-500/20 rounded text-[11px] text-emerald-400">
                            <CheckCircle2 className="w-3.5 h-3.5 inline mr-1" />
                            Monitor created — id <code className="text-emerald-300">{execResult.created_monitor.id}</code>
                        </div>
                    )}
                    {action.status === 'failed' && (
                        <div className="p-2 bg-red-500/[0.06] border border-red-500/20 rounded text-[11px] text-red-400">
                            <XCircle className="w-3.5 h-3.5 inline mr-1" />
                            Execution failed — {execResult.error || 'unknown error'}
                        </div>
                    )}
                    {action.status === 'rejected' && action.rejection_reason && (
                        <div className="p-2 bg-zinc-500/[0.06] border border-zinc-500/20 rounded text-[11px] text-zinc-400">
                            Rejected — {action.rejection_reason}
                        </div>
                    )}
                    {(action.approved_by || action.executed_at) && (
                        <div className="flex items-center gap-3 text-[10px] text-white/40">
                            {action.approved_by && <span>Approved by {action.approved_by}</span>}
                            {action.executed_at && (
                                <span>· {new Date(action.executed_at).toLocaleString()}</span>
                            )}
                        </div>
                    )}
                </div>
            )}

            {action.status === 'pending' && (
                isAdmin ? (
                    <div className="mt-3 flex items-center gap-2">
                        <Button
                            size="sm" className="bg-emerald-500 hover:bg-emerald-500/90 text-black font-semibold"
                            onClick={() => onApprove(action.id)} disabled={busy}
                            data-testid={`approve-${action.id}`}
                        >
                            {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" /> : <Check className="w-3.5 h-3.5 mr-1.5" />}
                            Approve & Execute
                        </Button>
                        <Button
                            size="sm" variant="outline"
                            className="border-white/10 text-white/70 hover:bg-white/5"
                            onClick={() => onReject(action.id)} disabled={busy}
                            data-testid={`reject-${action.id}`}
                        >
                            <X className="w-3.5 h-3.5 mr-1.5" /> Reject
                        </Button>
                    </div>
                ) : (
                    <div className="mt-3 flex items-center gap-2 text-[11px] text-amber-400/80">
                        <ShieldCheck className="w-3.5 h-3.5" />
                        Waiting for admin approval
                    </div>
                )
            )}
        </div>
    );
};

// ───────────── Message Bubble ─────────────

const MessageBubble = ({ msg, action, onApprove, onReject, isAdmin, busy }) => {
    const isUser = msg.role === 'user';
    return (
        <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''}`} data-testid={`message-${msg.id}`}>
            <div className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
                isUser ? 'bg-cyan-500/15' : 'bg-[#F5B841]/15'
            }`}>
                {isUser ? <User className="w-4 h-4 text-cyan-400" /> : <Bot className="w-4 h-4 text-[#F5B841]" />}
            </div>
            <div className={`max-w-[78%] ${isUser ? 'items-end' : 'items-start'} flex flex-col`}>
                <div className={`px-4 py-2.5 rounded-2xl ${
                    isUser
                        ? 'bg-cyan-500/15 border border-cyan-500/25 text-white rounded-tr-sm'
                        : 'bg-white/[0.04] border border-white/10 text-white/90 rounded-tl-sm'
                }`}>
                    <p className="text-sm whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                </div>
                {!isUser && action && (
                    <ActionCard
                        action={action} onApprove={onApprove} onReject={onReject}
                        isAdmin={isAdmin} busy={busy}
                    />
                )}
                <span className="text-[10px] text-white/30 mt-1 px-1">
                    {new Date(msg.created_at).toLocaleTimeString()}
                </span>
            </div>
        </div>
    );
};

// ───────────── Main Page ─────────────

export default function AICopilotPage() {
    const { user } = useAuth();
    const [sessions, setSessions] = useState([]);
    const [currentSession, setCurrentSession] = useState(null);
    const [messages, setMessages] = useState([]);
    const [actions, setActions] = useState({}); // action_id → action
    const [input, setInput] = useState('');
    const [sending, setSending] = useState(false);
    const [approving, setApproving] = useState(null);
    const scrollRef = useRef(null);
    const isAdmin = user?.role === 'admin';

    const SUGGESTIONS = [
        'Monitor https://api.example.com/health every 60s, alert if body contains "error" or response time > 2s',
        'Create a monitor for https://checkout.example.com that asserts $.status = "ok" on the response',
        'Run a check now on monitor abc-123 and tell me what failed',
        'Why is my monitor showing HTTP 200 but flagging as down?',
    ];

    useEffect(() => { loadSessions(); loadActions(); }, []);
    useEffect(() => {
        if (currentSession) loadMessages(currentSession.id);
    }, [currentSession?.id]);
    useEffect(() => {
        if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }, [messages, actions]);

    const loadSessions = async () => {
        try {
            const r = await fetch(`${API}/api/ai-copilot/sessions`, { headers: authHeaders() });
            const d = await r.json();
            setSessions(d.sessions || []);
        } catch { /* ignore */ }
    };

    const loadMessages = async (sid) => {
        try {
            const r = await fetch(`${API}/api/ai-copilot/sessions/${sid}/messages`, { headers: authHeaders() });
            const d = await r.json();
            setMessages(d.messages || []);
        } catch { /* ignore */ }
    };

    const loadActions = async () => {
        try {
            const r = await fetch(`${API}/api/ai-copilot/actions?limit=200`, { headers: authHeaders() });
            const d = await r.json();
            const map = {};
            (d.actions || []).forEach(a => { map[a.id] = a; });
            setActions(map);
        } catch { /* ignore */ }
    };

    const newSession = () => {
        setCurrentSession(null);
        setMessages([]);
    };

    const deleteSession = async (sid) => {
        if (!window.confirm('Delete this conversation?')) return;
        try {
            await fetch(`${API}/api/ai-copilot/sessions/${sid}`, {
                method: 'DELETE', headers: authHeaders(),
            });
            setSessions(s => s.filter(x => x.id !== sid));
            if (currentSession?.id === sid) newSession();
            toast.success('Conversation deleted');
        } catch {
            toast.error('Delete failed');
        }
    };

    const send = async () => {
        const msg = input.trim();
        if (!msg || sending) return;
        setInput('');
        setSending(true);
        try {
            const r = await fetch(`${API}/api/ai-copilot/chat`, {
                method: 'POST',
                headers: authHeaders(),
                body: JSON.stringify({ message: msg, session_id: currentSession?.id }),
            });
            if (!r.ok) throw new Error((await r.json()).detail || 'Chat failed');
            const d = await r.json();
            // Append both messages locally for snappy UX
            setMessages(prev => [...prev, d.user_message, d.assistant_message]);
            if (d.proposed_action) {
                setActions(prev => ({ ...prev, [d.proposed_action.id]: d.proposed_action }));
            }
            // First message → create session entry
            if (!currentSession) {
                const s = { id: d.session_id, title: msg.slice(0, 60), last_activity: new Date().toISOString(), message_count: 2 };
                setCurrentSession(s);
                setSessions(prev => [s, ...prev]);
            }
        } catch (e) {
            toast.error(e.message || 'AI chat failed');
        } finally {
            setSending(false);
        }
    };

    const approve = async (actionId) => {
        setApproving(actionId);
        try {
            const r = await fetch(`${API}/api/ai-copilot/actions/${actionId}/approve`, {
                method: 'POST', headers: authHeaders(),
            });
            const d = await r.json();
            if (!r.ok) throw new Error(d.detail || 'Approval failed');
            setActions(prev => ({ ...prev, [actionId]: d }));
            toast.success(d.status === 'executed' ? 'Approved & executed' : `Action ${d.status}`);
        } catch (e) {
            toast.error(e.message || 'Approval failed');
        } finally {
            setApproving(null);
        }
    };

    const reject = async (actionId) => {
        const reason = window.prompt('Reason for rejection (optional)') || '';
        setApproving(actionId);
        try {
            const r = await fetch(`${API}/api/ai-copilot/actions/${actionId}/reject`, {
                method: 'POST', headers: authHeaders(),
                body: JSON.stringify({ reason }),
            });
            const d = await r.json();
            if (!r.ok) throw new Error(d.detail || 'Rejection failed');
            setActions(prev => ({ ...prev, [actionId]: d }));
            toast.info('Action rejected');
        } catch (e) {
            toast.error(e.message || 'Rejection failed');
        } finally {
            setApproving(null);
        }
    };

    const pendingCount = Object.values(actions).filter(a => a.status === 'pending').length;

    if (!user) return <Navigate to="/login" replace />;

    return (
        <div className="h-[calc(100vh-6rem)] flex gap-4" data-testid="ai-copilot-page">
            {/* ───── Sidebar ───── */}
            <div className="w-64 shrink-0 flex flex-col gap-3">
                <Button
                    onClick={newSession}
                    className="bg-[#F5B841] hover:bg-[#F5B841]/90 text-black font-semibold"
                    data-testid="new-session-btn"
                >
                    <Plus className="w-4 h-4 mr-2" /> New Chat
                </Button>

                {pendingCount > 0 && (
                    <Card className="bg-amber-500/[0.06] border-amber-500/30">
                        <CardContent className="p-3">
                            <div className="flex items-center gap-2 text-xs text-amber-400">
                                <AlertCircle className="w-3.5 h-3.5" />
                                <span className="font-medium">{pendingCount} pending approval{pendingCount > 1 ? 's' : ''}</span>
                            </div>
                        </CardContent>
                    </Card>
                )}

                <div className="flex-1 min-h-0">
                    <div className="text-[10px] uppercase tracking-widest text-white/40 mb-2 px-1">Conversations</div>
                    <ScrollArea className="h-full">
                        <div className="space-y-1 pr-2">
                            {sessions.length === 0 && (
                                <p className="text-xs text-white/30 px-2 py-4 text-center">No conversations yet</p>
                            )}
                            {sessions.map(s => (
                                <button
                                    key={s.id}
                                    onClick={() => setCurrentSession(s)}
                                    data-testid={`session-${s.id}`}
                                    className={`w-full text-left px-3 py-2 rounded-lg transition-colors group ${
                                        currentSession?.id === s.id
                                            ? 'bg-[#F5B841]/10 border border-[#F5B841]/30'
                                            : 'hover:bg-white/5 border border-transparent'
                                    }`}
                                >
                                    <div className="flex items-start justify-between gap-2">
                                        <div className="min-w-0 flex-1">
                                            <div className="text-xs text-white truncate font-medium">{s.title}</div>
                                            <div className="text-[10px] text-white/35 flex items-center gap-1 mt-0.5">
                                                <Clock className="w-2.5 h-2.5" />
                                                {new Date(s.last_activity).toLocaleDateString()}
                                            </div>
                                        </div>
                                        <Trash2
                                            className="w-3 h-3 text-white/30 hover:text-red-400 opacity-0 group-hover:opacity-100 shrink-0"
                                            onClick={(e) => { e.stopPropagation(); deleteSession(s.id); }}
                                        />
                                    </div>
                                </button>
                            ))}
                        </div>
                    </ScrollArea>
                </div>
            </div>

            {/* ───── Chat pane ───── */}
            <Card className="flex-1 bg-[#0a0a0a] border-white/10 flex flex-col overflow-hidden">
                {/* Header */}
                <div className="p-4 border-b border-white/10 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-gradient-to-br from-[#F5B841]/20 to-amber-500/10 border border-[#F5B841]/30 rounded-lg">
                            <Bot className="w-5 h-5 text-[#F5B841]" />
                        </div>
                        <div>
                            <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                                FalconOps Copilot
                                <Badge className="text-[9px] bg-cyan-500/10 text-cyan-400 border-cyan-500/20">
                                    Claude Sonnet 4.5
                                </Badge>
                            </h2>
                            <p className="text-[11px] text-white/50">
                                Conversational monitoring · approval required for every change
                            </p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2">
                        <Button size="sm" variant="ghost" onClick={loadActions} data-testid="refresh-actions">
                            <RefreshCw className="w-3.5 h-3.5" />
                        </Button>
                        {!isAdmin && (
                            <Badge variant="outline" className="text-[10px] border-amber-500/30 text-amber-400">
                                View-only · admin required to approve
                            </Badge>
                        )}
                    </div>
                </div>

                {/* Messages area */}
                <div ref={scrollRef} className="flex-1 overflow-y-auto p-5 space-y-4">
                    {messages.length === 0 ? (
                        <div className="h-full flex items-center justify-center">
                            <div className="max-w-xl text-center">
                                <div className="w-14 h-14 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-[#F5B841]/20 to-amber-500/10 border border-[#F5B841]/30 flex items-center justify-center">
                                    <Sparkles className="w-7 h-7 text-[#F5B841]" />
                                </div>
                                <h3 className="text-lg font-semibold text-white mb-1">How can I help you today?</h3>
                                <p className="text-sm text-white/50 mb-6">
                                    Ask me to create monitors, triage alerts, or fix uptime issues.
                                    I'll propose changes and you approve them.
                                </p>
                                <div className="grid sm:grid-cols-2 gap-2">
                                    {SUGGESTIONS.map((s, i) => (
                                        <button
                                            key={i}
                                            onClick={() => setInput(s)}
                                            data-testid={`suggestion-${i}`}
                                            className="text-left p-3 bg-white/[0.02] border border-white/10 rounded-lg hover:bg-white/[0.04] hover:border-[#F5B841]/30 transition-all text-xs text-white/70"
                                        >
                                            <MessageSquare className="w-3 h-3 inline mr-1.5 text-[#F5B841]" />
                                            {s}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </div>
                    ) : (
                        messages.map(m => (
                            <MessageBubble
                                key={m.id} msg={m}
                                action={m.action_id ? actions[m.action_id] : null}
                                onApprove={approve} onReject={reject}
                                isAdmin={isAdmin}
                                busy={approving === m.action_id}
                            />
                        ))
                    )}
                </div>

                {/* Input */}
                <div className="p-4 border-t border-white/10">
                    <div className="flex items-center gap-2">
                        <Input
                            value={input}
                            onChange={(e) => setInput(e.target.value)}
                            onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
                            placeholder="Describe what you want to monitor or fix..."
                            className="flex-1 bg-black/40 border-white/10 text-white placeholder:text-white/30"
                            disabled={sending}
                            data-testid="chat-input"
                        />
                        <Button
                            onClick={send}
                            disabled={!input.trim() || sending}
                            className="bg-[#F5B841] hover:bg-[#F5B841]/90 text-black font-semibold"
                            data-testid="chat-send-btn"
                        >
                            {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                        </Button>
                    </div>
                    <div className="mt-2 flex items-center justify-between text-[10px] text-white/30">
                        <span><Zap className="w-2.5 h-2.5 inline mr-1" /> Every AI-proposed change needs admin approval</span>
                        <span><Activity className="w-2.5 h-2.5 inline mr-1" /> Audit log retained per session</span>
                    </div>
                </div>
            </Card>
        </div>
    );
}
