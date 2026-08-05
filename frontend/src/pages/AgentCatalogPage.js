import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent } from '../components/ui/card';
import { Badge } from '../components/ui/badge';
import { Button } from '../components/ui/button';
import { Bot, ShieldCheck, Plus } from 'lucide-react';

export const AgentCatalogPage = () => {
    const { api } = useAuth();
    const navigate = useNavigate();
    const [agents, setAgents] = useState([]);

    const load = useCallback(async () => {
        const res = await api.get('/v1/agent-builder/agents');
        setAgents(res.data.agents || []);
    }, [api]);

    useEffect(() => { load(); }, [load]);

    return (
        <div className="p-6 space-y-4">
            <div className="flex items-center justify-between">
                <h1 className="text-lg font-semibold text-white">Agent Catalog</h1>
                <Button size="sm" onClick={() => navigate('/ai/agent-builder')}><Plus className="w-3.5 h-3.5 mr-1" />New Agent</Button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {agents.map((a) => (
                    <Card key={a.agent_id} className="bg-white/5 border-white/10 hover:border-white/20 cursor-pointer"
                        onClick={() => navigate(`/ai/agent-builder/${a.agent_id}`)}>
                        <CardContent className="p-4 space-y-2">
                            <div className="flex items-center gap-2">
                                {a.is_rased_wrapper ? <ShieldCheck className="w-4 h-4 text-emerald-400" /> : <Bot className="w-4 h-4 text-violet-400" />}
                                <span className="text-sm font-semibold text-white">{a.name}</span>
                            </div>
                            <p className="text-xs text-white/50 line-clamp-2">{a.description}</p>
                            <div className="flex items-center gap-1.5 flex-wrap">
                                <Badge variant="outline" className="text-[10px]">{a.category}</Badge>
                                <Badge variant="outline" className="text-[10px]">{a.status}</Badge>
                                {a.is_rased_wrapper && <Badge variant="outline" className="text-[10px] text-emerald-300 border-emerald-500/30">RASED</Badge>}
                            </div>
                        </CardContent>
                    </Card>
                ))}
                {agents.length === 0 && <div className="text-white/40 text-sm">No agents yet.</div>}
            </div>
        </div>
    );
};

export default AgentCatalogPage;
