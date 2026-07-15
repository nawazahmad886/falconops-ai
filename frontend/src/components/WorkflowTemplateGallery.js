import React, { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Input } from './ui/input';
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from './ui/dialog';
import {
    Search, Copy, ChevronRight, Bot, Server, Activity, AlertTriangle,
    Rocket, Shield, Database, Network, Folder,
} from 'lucide-react';

const CATEGORY_ICONS = {
    infrastructure: Server,
    monitoring: Activity,
    incident: AlertTriangle,
    deployment: Rocket,
    security: Shield,
    database: Database,
    network: Network,
    agent: Bot,
    general: Folder,
};

const TemplateUseDialog = ({ template, onUse, onDone }) => {
    const [service, setService] = useState('');
    return (
        <div className="space-y-4">
            <div className="space-y-2">
                <label className="text-sm text-muted-foreground">Target Service</label>
                <Input
                    value={service}
                    onChange={(e) => setService(e.target.value)}
                    placeholder="Enter service name"
                    className="bg-muted/50"
                    data-testid="gallery-template-service-input"
                />
            </div>
            <Button
                className="w-full"
                onClick={() => { onUse(template.id, service); onDone(); }}
                data-testid="gallery-template-create-btn"
            >
                Create Workflow
            </Button>
        </div>
    );
};

export const WorkflowTemplateGallery = ({ open, onOpenChange, templates = [], onUseTemplate }) => {
    const [search, setSearch] = useState('');
    const [category, setCategory] = useState('all');
    const [activeTemplate, setActiveTemplate] = useState(null);

    const categories = useMemo(() => {
        const seen = new Set(templates.map(t => t.category));
        return ['all', ...Array.from(seen)];
    }, [templates]);

    const filtered = templates.filter(t => {
        if (category !== 'all' && t.category !== category) return false;
        if (!search.trim()) return true;
        const q = search.toLowerCase();
        return t.name.toLowerCase().includes(q) || (t.description || '').toLowerCase().includes(q);
    });

    return (
        <>
            <Dialog open={open} onOpenChange={onOpenChange}>
                <DialogContent className="max-w-5xl max-h-[85vh] overflow-y-auto bg-card border-border">
                    <DialogHeader>
                        <DialogTitle>Create workflow from template</DialogTitle>
                    </DialogHeader>

                    <div className="space-y-4">
                        <div className="relative">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                            <Input
                                value={search}
                                onChange={(e) => setSearch(e.target.value)}
                                placeholder="Search templates..."
                                className="bg-muted/50 pl-9"
                                data-testid="gallery-search-input"
                            />
                        </div>

                        <div className="flex items-center gap-2 flex-wrap">
                            {categories.map(cat => (
                                <Button
                                    key={cat}
                                    variant={category === cat ? 'default' : 'outline'}
                                    size="sm"
                                    onClick={() => setCategory(cat)}
                                    data-testid={`gallery-category-${cat}`}
                                >
                                    {cat === 'all' ? 'All' : cat}
                                </Button>
                            ))}
                        </div>

                        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {filtered.map((template) => {
                                const CatIcon = CATEGORY_ICONS[template.category] || Folder;
                                const isAgent = template.category === 'agent';
                                return (
                                    <Card
                                        key={template.id}
                                        className="bg-card/50 border-border/40 hover:border-primary/30 transition-colors"
                                        data-testid={`gallery-template-${template.id}`}
                                    >
                                        <CardHeader className="pb-2">
                                            <div className="flex items-start gap-3">
                                                <div className={`p-2 rounded-lg ${isAgent ? 'bg-purple-500/10' : 'bg-cyan-500/10'}`}>
                                                    <CatIcon className={`w-5 h-5 ${isAgent ? 'text-purple-400' : 'text-cyan-400'}`} />
                                                </div>
                                                <div>
                                                    <CardTitle className="text-base">{template.name}</CardTitle>
                                                    <div className="flex items-center gap-1 mt-1">
                                                        <Badge variant="secondary" className="text-[10px]">{template.category}</Badge>
                                                        {isAgent && (
                                                            <Badge className="text-[10px] bg-purple-500/15 text-purple-400 border-purple-500/30">
                                                                AI Agent
                                                            </Badge>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        </CardHeader>
                                        <CardContent>
                                            <p className="text-xs text-muted-foreground mb-3 line-clamp-2">{template.description}</p>
                                            <div className="space-y-1 mb-3">
                                                {template.steps?.slice(0, 3).map((step, idx) => (
                                                    <div key={idx} className="flex items-center gap-1 text-[11px] text-muted-foreground">
                                                        <ChevronRight className="w-3 h-3" />
                                                        {step.name}
                                                    </div>
                                                ))}
                                                {template.steps?.length > 3 && (
                                                    <div className="text-[11px] text-muted-foreground">+{template.steps.length - 3} more steps</div>
                                                )}
                                            </div>
                                            <Button
                                                size="sm"
                                                className="w-full"
                                                onClick={() => setActiveTemplate(template)}
                                                data-testid={`gallery-use-${template.id}`}
                                            >
                                                <Copy className="w-3.5 h-3.5 mr-2" />
                                                Use Template
                                            </Button>
                                        </CardContent>
                                    </Card>
                                );
                            })}
                            {filtered.length === 0 && (
                                <div className="col-span-full py-12 text-center text-muted-foreground text-sm">
                                    No templates match your search.
                                </div>
                            )}
                        </div>
                    </div>
                </DialogContent>
            </Dialog>

            <Dialog open={!!activeTemplate} onOpenChange={(v) => !v && setActiveTemplate(null)}>
                <DialogContent className="bg-card">
                    <DialogHeader>
                        <DialogTitle>Create from Template: {activeTemplate?.name}</DialogTitle>
                    </DialogHeader>
                    {activeTemplate && (
                        <TemplateUseDialog
                            template={activeTemplate}
                            onUse={onUseTemplate}
                            onDone={() => setActiveTemplate(null)}
                        />
                    )}
                </DialogContent>
            </Dialog>
        </>
    );
};

export default WorkflowTemplateGallery;
