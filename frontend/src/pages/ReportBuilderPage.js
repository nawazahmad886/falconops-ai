import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription,
} from '../components/ui/dialog';
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import { toast } from 'sonner';
import {
    Layers, Plus, Save, Trash2, Edit, Copy, RefreshCw, GripVertical,
    ArrowUp, ArrowDown, X, FolderOpen, Sparkles, FileDown, Eye,
    Image as ImageIcon, Type, Grid3x3, Table as TableIcon,
    BarChart3, Gauge as GaugeIcon, TrendingUp, AlertTriangle,
    Minus, FileText,
} from 'lucide-react';

const SECTION_ICONS = {
    header_logo: ImageIcon,
    title: Type,
    kpi_banner: Grid3x3,
    exec_summary: Sparkles,
    sla_table: TableIcon,
    severity_chart: BarChart3,
    sla_gauge_chart: GaugeIcon,
    top_rules_chart: TrendingUp,
    alert_table: AlertTriangle,
    custom_text: Edit,
    page_break: Minus,
    footer: FileText,
};

const SECTION_COLORS = {
    header_logo: 'text-indigo-400 bg-indigo-500/10 border-indigo-500/20',
    title: 'text-white bg-white/5 border-white/10',
    kpi_banner: 'text-[#00E0FF] bg-[#00E0FF]/10 border-[#00E0FF]/20',
    exec_summary: 'text-pink-400 bg-pink-500/10 border-pink-500/20',
    sla_table: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20',
    severity_chart: 'text-orange-400 bg-orange-500/10 border-orange-500/20',
    sla_gauge_chart: 'text-[#00E0FF] bg-[#00E0FF]/10 border-[#00E0FF]/20',
    top_rules_chart: 'text-purple-400 bg-purple-500/10 border-purple-500/20',
    alert_table: 'text-red-400 bg-red-500/10 border-red-500/20',
    custom_text: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
    page_break: 'text-white/50 bg-white/5 border-white/10',
    footer: 'text-white/50 bg-white/5 border-white/10',
};

export default function ReportBuilderPage() {
    const { api } = useAuth();
    const [templates, setTemplates] = useState([]);
    const [currentId, setCurrentId] = useState(null);
    const [name, setName] = useState('My Weekly Report Template');
    const [description, setDescription] = useState('');
    const [sections, setSections] = useState([]);
    const [catalog, setCatalog] = useState([]);
    const [defaultSections, setDefaultSections] = useState([]);
    const [showCatalog, setShowCatalog] = useState(false);
    const [showLoad, setShowLoad] = useState(false);
    const [showEdit, setShowEdit] = useState(false);
    const [editingIdx, setEditingIdx] = useState(-1);
    const [editingSection, setEditingSection] = useState(null);
    const [saving, setSaving] = useState(false);
    const [previewing, setPreviewing] = useState(false);
    const [dragIdx, setDragIdx] = useState(-1);

    const fetchAll = useCallback(async () => {
        try {
            const [c, l] = await Promise.all([
                api.get('/report-templates/catalog'),
                api.get('/report-templates/list'),
            ]);
            setCatalog(c.data?.sections || []);
            setDefaultSections(c.data?.default_sections || []);
            setTemplates(l.data || []);
        } catch (e) { console.error(e); }
    }, [api]);

    useEffect(() => { fetchAll(); }, [fetchAll]);

    const addSection = (stype, label) => {
        setSections([...sections, {
            section_type: stype,
            title: '',
            content: '',
            config: {},
        }]);
        setShowCatalog(false);
        toast.success(`Added ${label}`);
    };

    const removeSection = (idx) => {
        setSections(sections.filter((_, i) => i !== idx));
    };

    const moveSection = (idx, dir) => {
        const newSections = [...sections];
        const newIdx = idx + dir;
        if (newIdx < 0 || newIdx >= newSections.length) return;
        [newSections[idx], newSections[newIdx]] = [newSections[newIdx], newSections[idx]];
        setSections(newSections);
    };

    const onDragStart = (idx) => setDragIdx(idx);
    const onDragOver = (e) => e.preventDefault();
    const onDrop = (idx) => {
        if (dragIdx === -1 || dragIdx === idx) return;
        const newSections = [...sections];
        const [moved] = newSections.splice(dragIdx, 1);
        newSections.splice(idx, 0, moved);
        setSections(newSections);
        setDragIdx(-1);
    };

    const openEdit = (idx) => {
        setEditingIdx(idx);
        setEditingSection({ ...sections[idx] });
        setShowEdit(true);
    };
    const saveEdit = () => {
        const copy = [...sections];
        copy[editingIdx] = editingSection;
        setSections(copy);
        setShowEdit(false);
        toast.success('Section updated');
    };

    const loadDefault = () => {
        setCurrentId(null);
        setName('Default Weekly Template');
        setDescription('Full enterprise layout');
        setSections(defaultSections.map(s => ({ ...s })));
        toast.success('Default template loaded');
    };

    const clearAll = () => {
        setCurrentId(null);
        setName('New Template');
        setDescription('');
        setSections([]);
    };

    const saveTemplate = async () => {
        if (sections.length === 0) return toast.error('Add at least one section');
        setSaving(true);
        try {
            const payload = { name, description, sections };
            if (currentId) {
                await api.put(`/report-templates/${currentId}`, payload);
                toast.success('Template updated');
            } else {
                const res = await api.post('/report-templates/create', payload);
                setCurrentId(res.data?.template_id);
                toast.success('Template saved');
            }
            await fetchAll();
        } catch (e) {
            toast.error(`Save failed: ${e.response?.data?.detail || e.message}`);
        }
        setSaving(false);
    };

    const loadTemplate = (t) => {
        setCurrentId(t.template_id);
        setName(t.name);
        setDescription(t.description || '');
        setSections(t.sections || []);
        setShowLoad(false);
        toast.success(`Loaded "${t.name}"`);
    };

    const deleteTemplate = async (id) => {
        if (!window.confirm('Delete this template?')) return;
        try {
            await api.delete(`/report-templates/${id}`);
            if (currentId === id) clearAll();
            await fetchAll();
            toast.success('Deleted');
        } catch (e) {
            toast.error(`Delete failed: ${e.message}`);
        }
    };

    const previewPdf = async () => {
        if (!currentId) {
            toast.error('Save the template first to preview PDF');
            return;
        }
        setPreviewing(true);
        try {
            const res = await api.post('/weekly-reports/generate/auto', {
                days: 7,
                include_pdf: true,
                executive: true,
                template_id: currentId,
            });
            const reportId = res.data?.report_id;
            if (!reportId) throw new Error('No report id');
            // Download PDF
            const token = localStorage.getItem('falconToken');
            const pdfRes = await fetch(
                `${process.env.REACT_APP_BACKEND_URL}/api/weekly-reports/${reportId}/download/pdf`,
                { headers: { 'Authorization': `Bearer ${token}` } }
            );
            if (!pdfRes.ok) throw new Error('PDF download failed');
            const blob = await pdfRes.blob();
            const url = window.URL.createObjectURL(blob);
            window.open(url, '_blank');
            toast.success('PDF preview opened');
        } catch (e) {
            toast.error(`Preview failed: ${e.response?.data?.detail || e.message}`);
        }
        setPreviewing(false);
    };

    return (
        <div className="space-y-5" data-testid="report-builder-page">
            {/* Header */}
            <div className="flex items-center justify-between flex-wrap gap-3">
                <div className="flex items-center gap-3">
                    <Layers className="w-6 h-6 text-[#F5B841]" />
                    <div className="space-y-1">
                        <Input
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            className="bg-[#0D1117] border-white/10 text-white font-semibold w-72"
                            placeholder="Template name"
                            data-testid="template-name-input"
                        />
                        <Input
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            placeholder="Description (optional)"
                            className="bg-[#0D1117] border-white/10 text-xs text-white/60 w-72"
                            data-testid="template-description-input"
                        />
                    </div>
                    {currentId && (
                        <Badge variant="outline" className="border-white/10 text-white/50 text-[10px]">
                            {currentId}
                        </Badge>
                    )}
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                    <Button size="sm" variant="ghost" onClick={loadDefault} data-testid="load-default-btn">
                        <Sparkles className="w-4 h-4 mr-2" /> Default Layout
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setShowLoad(true)} data-testid="open-load-btn">
                        <FolderOpen className="w-4 h-4 mr-2" /> Load
                    </Button>
                    <Button size="sm" variant="ghost" onClick={clearAll} data-testid="new-template-btn">
                        <Plus className="w-4 h-4 mr-2" /> New
                    </Button>
                    <Button size="sm" variant="outline" className="border-[#F5B841]/30 text-[#F5B841]"
                        onClick={previewPdf} disabled={previewing || !currentId}
                        data-testid="preview-pdf-btn"
                    >
                        {previewing ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <FileDown className="w-4 h-4 mr-2" />}
                        Preview PDF
                    </Button>
                    <Button
                        onClick={saveTemplate}
                        disabled={saving}
                        className="bg-[#00E0FF] hover:bg-[#00E0FF]/90 text-black"
                        size="sm"
                        data-testid="save-template-btn"
                    >
                        {saving ? <RefreshCw className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                        Save
                    </Button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-4 gap-5">
                {/* Section palette */}
                <Card className="bg-[#0D1117] border-white/5 lg:col-span-1">
                    <CardHeader>
                        <CardTitle className="text-xs flex items-center gap-2">
                            <Layers className="w-4 h-4 text-[#00E0FF]" />
                            Section Palette
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2">
                        {catalog.map((s) => {
                            const Icon = SECTION_ICONS[s.type] || Edit;
                            const cls = SECTION_COLORS[s.type] || 'text-white bg-white/5';
                            return (
                                <button
                                    key={s.type}
                                    onClick={() => addSection(s.type, s.label)}
                                    className="w-full flex items-center gap-2 p-2 rounded-lg border border-white/10 bg-white/[0.02] hover:bg-white/[0.06] text-left transition-colors"
                                    data-testid={`palette-${s.type}`}
                                >
                                    <div className={`p-1.5 rounded ${cls}`}>
                                        <Icon className="w-3.5 h-3.5" />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-xs text-white/80 leading-tight">{s.label}</p>
                                        <p className="text-[9px] text-white/30 capitalize">{s.category}</p>
                                    </div>
                                    <Plus className="w-3 h-3 text-white/30" />
                                </button>
                            );
                        })}
                    </CardContent>
                </Card>

                {/* Canvas */}
                <Card className="bg-[#0D1117] border-white/5 lg:col-span-3">
                    <CardHeader>
                        <CardTitle className="text-xs flex items-center justify-between">
                            <span className="flex items-center gap-2">
                                <Edit className="w-4 h-4 text-[#F5B841]" />
                                Canvas ({sections.length} sections)
                            </span>
                            <span className="text-[10px] text-white/40 font-normal">Drag to reorder · Click ✎ to edit</span>
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        {sections.length === 0 ? (
                            <div className="text-center py-16 border-2 border-dashed border-white/10 rounded-lg" data-testid="empty-canvas">
                                <Layers className="w-12 h-12 mx-auto text-white/20 mb-3" />
                                <p className="text-white/50 text-sm">Canvas is empty</p>
                                <p className="text-xs text-white/30 mt-1">Add sections from the palette or load the default layout</p>
                                <Button onClick={loadDefault} className="mt-4 bg-[#00E0FF]/10 text-[#00E0FF] border border-[#00E0FF]/30 hover:bg-[#00E0FF]/20">
                                    <Sparkles className="w-4 h-4 mr-2" /> Load Default
                                </Button>
                            </div>
                        ) : (
                            <div className="space-y-2" data-testid="canvas-sections">
                                {sections.map((s, idx) => {
                                    const Icon = SECTION_ICONS[s.section_type] || Edit;
                                    const cls = SECTION_COLORS[s.section_type] || 'text-white bg-white/5';
                                    const meta = catalog.find(c => c.type === s.section_type);
                                    return (
                                        <div
                                            key={idx}
                                            draggable
                                            onDragStart={() => onDragStart(idx)}
                                            onDragOver={onDragOver}
                                            onDrop={() => onDrop(idx)}
                                            className="flex items-center gap-2 p-2.5 rounded-lg border border-white/10 bg-white/[0.02] hover:bg-white/[0.04] cursor-move"
                                            data-testid={`canvas-section-${idx}`}
                                        >
                                            <GripVertical className="w-4 h-4 text-white/30 shrink-0" />
                                            <div className="text-[10px] text-white/40 font-mono w-5">{idx + 1}</div>
                                            <div className={`p-1.5 rounded ${cls}`}>
                                                <Icon className="w-3.5 h-3.5" />
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <p className="text-xs text-white font-medium truncate">
                                                    {meta?.label || s.section_type}
                                                </p>
                                                {(s.section_type === 'custom_text' && (s.title || s.content)) && (
                                                    <p className="text-[10px] text-white/40 truncate mt-0.5">
                                                        {s.title && <span className="text-amber-400">{s.title}: </span>}
                                                        {s.content?.slice(0, 80)}
                                                    </p>
                                                )}
                                            </div>
                                            <div className="flex items-center gap-0.5 shrink-0">
                                                <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => moveSection(idx, -1)} disabled={idx === 0}>
                                                    <ArrowUp className="w-3 h-3" />
                                                </Button>
                                                <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => moveSection(idx, 1)} disabled={idx === sections.length - 1}>
                                                    <ArrowDown className="w-3 h-3" />
                                                </Button>
                                                <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => openEdit(idx)} data-testid={`edit-section-${idx}`}>
                                                    <Edit className="w-3 h-3" />
                                                </Button>
                                                <Button size="icon" variant="ghost" className="h-7 w-7 text-red-400 hover:bg-red-500/10"
                                                    onClick={() => removeSection(idx)} data-testid={`remove-section-${idx}`}>
                                                    <X className="w-3 h-3" />
                                                </Button>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </CardContent>
                </Card>
            </div>

            {/* Load Dialog */}
            <Dialog open={showLoad} onOpenChange={setShowLoad}>
                <DialogContent className="bg-[#0D1117] border-white/10 max-w-xl">
                    <DialogHeader>
                        <DialogTitle className="flex items-center gap-2">
                            <FolderOpen className="w-5 h-5 text-[#F5B841]" />
                            My Templates ({templates.length})
                        </DialogTitle>
                        <DialogDescription className="text-white/40 text-xs">
                            Load a saved template or delete old ones.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-2 max-h-[60vh] overflow-y-auto">
                        {templates.length === 0 && <p className="text-center text-white/40 py-8 text-sm">No templates saved</p>}
                        {templates.map((t) => (
                            <div
                                key={t.template_id}
                                className="flex items-center justify-between p-3 rounded-lg border border-white/10 bg-white/[0.02] hover:bg-white/[0.05]"
                                data-testid={`saved-template-${t.template_id}`}
                            >
                                <div className="flex-1 min-w-0 cursor-pointer" onClick={() => loadTemplate(t)}>
                                    <p className="text-sm text-white font-medium truncate">{t.name}</p>
                                    {t.description && <p className="text-[10px] text-white/40 truncate">{t.description}</p>}
                                    <p className="text-[10px] text-white/40 mt-0.5">
                                        {t.sections?.length || 0} sections · Updated {new Date(t.updated_at).toLocaleDateString()}
                                    </p>
                                </div>
                                <Button size="icon" variant="ghost" onClick={() => deleteTemplate(t.template_id)}
                                    className="text-red-400 hover:bg-red-500/10"
                                    data-testid={`delete-template-${t.template_id}`}>
                                    <Trash2 className="w-4 h-4" />
                                </Button>
                            </div>
                        ))}
                    </div>
                </DialogContent>
            </Dialog>

            {/* Edit Section Dialog */}
            <Dialog open={showEdit} onOpenChange={setShowEdit}>
                <DialogContent className="bg-[#0D1117] border-white/10 max-w-lg">
                    <DialogHeader>
                        <DialogTitle>Edit Section</DialogTitle>
                        <DialogDescription className="text-white/40 text-xs">
                            {editingSection?.section_type}
                        </DialogDescription>
                    </DialogHeader>
                    {editingSection && (
                        <div className="space-y-3">
                            {(editingSection.section_type === 'custom_text' || editingSection.section_type === 'title') && (
                                <>
                                    <div>
                                        <Label className="text-xs text-white/60 mb-1 block">Title (optional)</Label>
                                        <Input
                                            value={editingSection.title || ''}
                                            onChange={(e) => setEditingSection({ ...editingSection, title: e.target.value })}
                                            className="bg-[#161B22] border-white/10"
                                            data-testid="edit-section-title"
                                        />
                                    </div>
                                    {editingSection.section_type === 'custom_text' && (
                                        <div>
                                            <Label className="text-xs text-white/60 mb-1 block">Content</Label>
                                            <Textarea
                                                value={editingSection.content || ''}
                                                onChange={(e) => setEditingSection({ ...editingSection, content: e.target.value })}
                                                rows={5}
                                                className="bg-[#161B22] border-white/10"
                                                data-testid="edit-section-content"
                                            />
                                        </div>
                                    )}
                                    {editingSection.section_type === 'title' && (
                                        <div>
                                            <Label className="text-xs text-white/60 mb-1 block">Custom Title Line (optional, overrides default)</Label>
                                            <Input
                                                value={editingSection.config?.custom_title || ''}
                                                onChange={(e) => setEditingSection({
                                                    ...editingSection,
                                                    config: { ...(editingSection.config || {}), custom_title: e.target.value }
                                                })}
                                                placeholder={`Company · Weekly SOC & AIOps Report`}
                                                className="bg-[#161B22] border-white/10"
                                                data-testid="edit-custom-title"
                                            />
                                        </div>
                                    )}
                                </>
                            )}
                            {!['custom_text', 'title'].includes(editingSection.section_type) && (
                                <p className="text-xs text-white/50">This section has no editable properties. It renders with live data.</p>
                            )}
                            <Button onClick={saveEdit} className="w-full bg-[#00E0FF] text-black" data-testid="save-section-edit-btn">
                                <Save className="w-4 h-4 mr-2" /> Save Section
                            </Button>
                        </div>
                    )}
                </DialogContent>
            </Dialog>
        </div>
    );
}
