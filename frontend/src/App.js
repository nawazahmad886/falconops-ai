import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Toaster } from './components/ui/sonner';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LanguageProvider } from './context/LanguageContext';
import { GlobalFiltersProvider } from './context/GlobalFiltersContext';
import { ThemeProvider } from './context/ThemeContext';
import { LandingPage } from './pages/LandingPage';
import { LoginPage, RegisterPage } from './pages/AuthPages';
import { DashboardPage } from './pages/DashboardPage';
import { RasedPage } from './pages/RasedPage';
import IncidentCommanderPage from './pages/IncidentCommanderPage';
import { AlertsPage } from './pages/AlertsPage';
import { IncidentsPage } from './pages/IncidentsPage';
import { RunbooksPage } from './pages/RunbooksPage';
import { AnalyticsPage } from './pages/AnalyticsPage';
import { SettingsPage } from './pages/SettingsPage';
import { AboutPage } from './pages/AboutPage';
import { ServicesPage } from './pages/ServicesPage';
import { TrainingPage } from './pages/TrainingPage';
import { ContactPage } from './pages/ContactPage';
import { AIPlatformPage } from './pages/AIPlatformPage';
import { SecurityPage } from './pages/SecurityPage';
import { MonitoringPage } from './pages/MonitoringPage';
import { HoneycombDashboardPage } from './pages/HoneycombDashboardPage';
import { TopologyPage } from './pages/TopologyPage';
import { ReportsPage } from './pages/ReportsPage';
import { ExecutiveReportsPage } from './pages/ExecutiveReportsPage';
import { APMPage } from './pages/APMPage';
import { ServerMonitoringPage } from './pages/ServerMonitoringPage';
import { AdminPage } from './pages/AdminPage';
import { LogsPage } from './pages/LogsPage';
import { DownloadPage } from './pages/DownloadPage';
import { EventAnalyzerPage } from './pages/EventAnalyzerPage';
import { IntelligencePage } from './pages/IntelligencePage';
import { WallboardPage } from './pages/WallboardPage';
import MetricsExplorerPage from './pages/MetricsExplorerPage';
import { AlertEnginePage } from './pages/AlertEnginePage';
import { AlertRespondPage } from './pages/AlertRespondPage';
import { IncidentEnginePage } from './pages/IncidentEnginePage';
import { CapacityPredictionPage } from './pages/CapacityPredictionPage';
import AIOPsBrainPage from './pages/AIOPsBrainPage';
import NOCDashboardPage from './pages/NOCDashboardPage';
import { CoreAIOpsPage } from './pages/CoreAIOpsPage';
import { DatabaseMonitoringPage } from './pages/DatabaseMonitoringPage';
import { HealthRulesPage } from './pages/HealthRulesPage';
import SyntheticMonitoringPage from './pages/SyntheticMonitoringPage';
import SelfMonitoringPage from './pages/SelfMonitoringPage';
import SecurityMonitoringPage from './pages/SecurityMonitoringPage';
import ExecutiveSecurityDashboardPage from './pages/ExecutiveSecurityDashboardPage';
import UEBAPage from './pages/UEBAPage';
import AttackSimulatorPage from './pages/AttackSimulatorPage';
import IntegrationsPage from './pages/IntegrationsPage';
import RemediationPage from './pages/RemediationPage';
import ImpactAnalysisPage from './pages/ImpactAnalysisPage';
import SOCLiveFeedPage from './pages/SOCLiveFeedPage';
import AWSConnectorsPage from './pages/AWSConnectorsPage';
import KafkaPipelinePage from './pages/KafkaPipelinePage';
import RBACPage from './pages/RBACPage';
import QueryAnalyzerPage from './pages/QueryAnalyzerPage';
import UptimeMonitorPage from './pages/UptimeMonitorPage';
import TenantsPage from './pages/TenantsPage';
import DBAgentPage from './pages/DBAgentPage';
import BillingPage from './pages/BillingPage';
import CheckNodesPage from './pages/CheckNodesPage';
import SLADashboardPage from './pages/SLADashboardPage';
import ServiceMapPage from './pages/ServiceMapPage';
import DetectionRulesPage from './pages/DetectionRulesPage';
import AIAgentsPage from './pages/AIAgentsPage';
import AICopilotPage from './pages/AICopilotPage';
import AdminControlConsole from './pages/AdminControlConsole';
import AIInsightPanel from './pages/AIInsightPanel';
import AlertCorrelationPage from './pages/AlertCorrelationPage';
import K8sHealingPage from './pages/K8sHealingPage';
import AdminConsolePage from './pages/AdminConsolePage';
import WeeklyReportsPage from './pages/WeeklyReportsPage';
import CustomDashboardPage from './pages/CustomDashboardPage';
import TenantBrandingPage from './pages/TenantBrandingPage';
import ScheduledReportsPage from './pages/ScheduledReportsPage';
import TenantSchedulesPage from './pages/TenantSchedulesPage';
import ReportBuilderPage from './pages/ReportBuilderPage';
import PublicPortalPage from './pages/PublicPortalPage';
import APMTracesPage from './pages/APMTracesPage';
import LiveCallFlowPage from './pages/LiveCallFlowPage';
import ProblemsPage from './pages/ProblemsPage';
import ResourceExplorerPage from './pages/ResourceExplorerPage';
import ResourceDetailPage from './pages/ResourceDetailPage';
import AgenticWorkflowPage from './pages/AgenticWorkflowPage';
import ControlCenterPage from './pages/ControlCenterPage';
import ServiceDetailPage from './pages/ServiceDetailPage';
import APMQuickstartPage from './pages/APMQuickstartPage';
import PricingPage from './pages/PricingPage';
import AdminPlansPage from './pages/AdminPlansPage';
import AdminEmailTemplatesPage from './pages/AdminEmailTemplatesPage';
import AdminLeadsPage from './pages/AdminLeadsPage';
import AutomationTemplatesPage from './pages/AutomationTemplatesPage';
import AWSDeployWizardPage from './pages/AWSDeployWizardPage';
import AIMonitoringPage from './pages/AIMonitoringPage';
import AIObservabilityPage from './pages/AIObservabilityPage';
import AskFalconOpsPage from './pages/AskFalconOpsPage';
import OneAgentFleetPage from './pages/OneAgentFleetPage';
import { EnterpriseLayout } from './layouts/EnterpriseLayout';
import './App.css';

// Protected Route wrapper with Enterprise Layout
const ProtectedRoute = ({ children }) => {
    const { isAuthenticated, loading } = useAuth();
    
    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <div className="w-10 h-10 border-4 border-primary/30 border-t-primary rounded-full animate-spin" />
            </div>
        );
    }
    
    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }
    
    return <EnterpriseLayout>{children}</EnterpriseLayout>;
};

// Protected Route without layout (for fullscreen pages like wallboard)
const ProtectedRouteNoLayout = ({ children }) => {
    const { isAuthenticated, loading } = useAuth();
    
    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <div className="w-10 h-10 border-4 border-primary/30 border-t-primary rounded-full animate-spin" />
            </div>
        );
    }
    
    if (!isAuthenticated) {
        return <Navigate to="/login" replace />;
    }
    
    return children;
};

// Public Route wrapper (redirect to dashboard if logged in).
// IMPORTANT: when the user lands here with `?plan=<id>` (paid-plan funnel from /pricing
// or landing), forward authenticated users to the billing/checkout page instead of
// dropping them on /dashboard. Trial/free fall through to /dashboard as before.
const PublicRoute = ({ children }) => {
    const { isAuthenticated, loading } = useAuth();
    const location = useLocation();
    
    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-background">
                <div className="w-10 h-10 border-4 border-primary/30 border-t-primary rounded-full animate-spin" />
            </div>
        );
    }
    
    if (isAuthenticated) {
        const plan = new URLSearchParams(location.search).get('plan');
        const normalized = (plan || '').toLowerCase();
        if (normalized && !['trial', 'free'].includes(normalized)) {
            return <Navigate to={`/billing?plan=${encodeURIComponent(normalized)}`} replace />;
        }
        return <Navigate to="/dashboard" replace />;
    }
    
    return children;
};

const AppRoutes = () => {
    return (
        <Routes>
            {/* Public Routes */}
            <Route path="/" element={<LandingPage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="/services" element={<ServicesPage />} />
            <Route path="/ai-platform" element={<AIPlatformPage />} />
            <Route path="/security" element={<SecurityPage />} />
            <Route path="/training" element={<TrainingPage />} />
            <Route path="/contact" element={<ContactPage />} />
            <Route 
                path="/login" 
                element={
                    <PublicRoute>
                        <LoginPage />
                    </PublicRoute>
                } 
            />
            <Route 
                path="/register" 
                element={
                    <PublicRoute>
                        <RegisterPage />
                    </PublicRoute>
                } 
            />
            <Route 
                path="/signup" 
                element={
                    <PublicRoute>
                        <RegisterPage />
                    </PublicRoute>
                } 
            />
            
            {/* Protected Routes */}
            <Route 
                path="/dashboard" 
                element={
                    <ProtectedRoute>
                        <DashboardPage />
                    </ProtectedRoute>
                } 
            />
            <Route
                path="/alerts"
                element={
                    <ProtectedRoute>
                        <AlertsPage />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/rased"
                element={
                    <ProtectedRoute>
                        <RasedPage />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/incident-commander"
                element={
                    <ProtectedRoute>
                        <IncidentCommanderPage />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/incidents"
                element={
                    <ProtectedRoute>
                        <IncidentsPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/runbooks" 
                element={
                    <ProtectedRoute>
                        <RunbooksPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/analytics" 
                element={
                    <ProtectedRoute>
                        <AnalyticsPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/monitoring" 
                element={
                    <ProtectedRoute>
                        <MonitoringPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/honeycomb" 
                element={
                    <ProtectedRoute>
                        <HoneycombDashboardPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/topology" 
                element={
                    <ProtectedRoute>
                        <TopologyPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/reports" 
                element={
                    <ProtectedRoute>
                        <ExecutiveReportsPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/reports/scheduled" 
                element={
                    <ProtectedRoute>
                        <ReportsPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/apm" 
                element={
                    <ProtectedRoute>
                        <APMPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/servers" 
                element={
                    <ProtectedRoute>
                        <ServerMonitoringPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/logs" 
                element={
                    <ProtectedRoute>
                        <LogsPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/settings" 
                element={
                    <ProtectedRoute>
                        <SettingsPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/admin" 
                element={
                    <ProtectedRoute>
                        <AdminPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/download" 
                element={
                    <ProtectedRoute>
                        <DownloadPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/event-analyzer" 
                element={
                    <ProtectedRoute>
                        <EventAnalyzerPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/intelligence" 
                element={
                    <ProtectedRoute>
                        <IntelligencePage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/wallboard" 
                element={
                    <ProtectedRouteNoLayout>
                        <WallboardPage />
                    </ProtectedRouteNoLayout>
                } 
            />
            <Route 
                path="/metrics-explorer" 
                element={
                    <ProtectedRoute>
                        <MetricsExplorerPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/alert-engine" 
                element={
                    <ProtectedRoute>
                        <AlertEnginePage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/alert-respond" 
                element={
                    <ProtectedRoute>
                        <AlertRespondPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/incident-engine" 
                element={
                    <ProtectedRoute>
                        <IncidentEnginePage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/capacity-prediction" 
                element={
                    <ProtectedRoute>
                        <CapacityPredictionPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/aiops-brain" 
                element={
                    <ProtectedRoute>
                        <AIOPsBrainPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/noc-dashboard" 
                element={
                    <ProtectedRoute>
                        <NOCDashboardPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/core-aiops" 
                element={
                    <ProtectedRoute>
                        <CoreAIOpsPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/db-monitoring" 
                element={
                    <ProtectedRoute>
                        <DatabaseMonitoringPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/health-rules" 
                element={
                    <ProtectedRoute>
                        <HealthRulesPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/synthetic-monitoring" 
                element={
                    <ProtectedRoute>
                        <SyntheticMonitoringPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/self-monitoring" 
                element={
                    <ProtectedRoute>
                        <SelfMonitoringPage />
                    </ProtectedRoute>
                } 
            />
            <Route
                path="/security-monitoring"
                element={
                    <ProtectedRoute>
                        <SecurityMonitoringPage />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/executive-security"
                element={
                    <ProtectedRoute>
                        <ExecutiveSecurityDashboardPage />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/ueba"
                element={
                    <ProtectedRoute>
                        <UEBAPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/attack-simulator" 
                element={
                    <ProtectedRoute>
                        <AttackSimulatorPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/integrations" 
                element={
                    <ProtectedRoute>
                        <IntegrationsPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/remediation" 
                element={
                    <ProtectedRoute>
                        <RemediationPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/impact-analysis" 
                element={
                    <ProtectedRoute>
                        <ImpactAnalysisPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/soc-live-feed" 
                element={
                    <ProtectedRoute>
                        <SOCLiveFeedPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/aws-connectors" 
                element={
                    <ProtectedRoute>
                        <AWSConnectorsPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/kafka-pipeline" 
                element={
                    <ProtectedRoute>
                        <KafkaPipelinePage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/rbac" 
                element={
                    <ProtectedRoute>
                        <RBACPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/query-analyzer" 
                element={
                    <ProtectedRoute>
                        <QueryAnalyzerPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/uptime-monitor" 
                element={
                    <ProtectedRoute>
                        <UptimeMonitorPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/tenants" 
                element={
                    <ProtectedRoute>
                        <TenantsPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/db-agents" 
                element={
                    <ProtectedRoute>
                        <DBAgentPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/billing" 
                element={
                    <ProtectedRoute>
                        <BillingPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/check-nodes" 
                element={
                    <ProtectedRoute>
                        <CheckNodesPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/sla-dashboard" 
                element={
                    <ProtectedRoute>
                        <SLADashboardPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/service-map" 
                element={
                    <ProtectedRoute>
                        <ServiceMapPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/detection-rules" 
                element={
                    <ProtectedRoute>
                        <DetectionRulesPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/ai-agents" 
                element={
                    <ProtectedRoute>
                        <AIAgentsPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/ai-copilot" 
                element={
                    <ProtectedRoute>
                        <AICopilotPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/admin/control-console" 
                element={
                    <ProtectedRoute>
                        <AdminControlConsole />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/ai-engine" 
                element={
                    <ProtectedRoute>
                        <AIInsightPanel />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/alert-correlation" 
                element={
                    <ProtectedRoute>
                        <AlertCorrelationPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/k8s-healing" 
                element={
                    <ProtectedRoute>
                        <K8sHealingPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/admin-console" 
                element={
                    <ProtectedRoute>
                        <AdminConsolePage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/weekly-reports" 
                element={
                    <ProtectedRoute>
                        <WeeklyReportsPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/custom-dashboard" 
                element={
                    <ProtectedRoute>
                        <CustomDashboardPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/tenant-branding" 
                element={
                    <ProtectedRoute>
                        <TenantBrandingPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/scheduled-reports" 
                element={
                    <ProtectedRoute>
                        <ScheduledReportsPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/tenant-schedules" 
                element={
                    <ProtectedRoute>
                        <TenantSchedulesPage />
                    </ProtectedRoute>
                } 
            />
            <Route 
                path="/report-builder" 
                element={
                    <ProtectedRoute>
                        <ReportBuilderPage />
                    </ProtectedRoute>
                } 
            />
            <Route
                path="/apm-traces"
                element={
                    <ProtectedRoute>
                        <APMTracesPage />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/live-call-flow"
                element={
                    <ProtectedRoute>
                        <LiveCallFlowPage />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/problems"
                element={
                    <ProtectedRoute>
                        <ProblemsPage />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/resources"
                element={
                    <ProtectedRoute>
                        <ResourceExplorerPage />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/resources/:resourceId"
                element={
                    <ProtectedRoute>
                        <ResourceDetailPage />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/agentic-workflow"
                element={
                    <ProtectedRoute>
                        <AgenticWorkflowPage />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/control-center"
                element={
                    <ProtectedRoute>
                        <ControlCenterPage />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/apm/services/:serviceName"
                element={
                    <ProtectedRoute>
                        <ServiceDetailPage />
                    </ProtectedRoute>
                }
            />
            <Route 
                path="/apm-quickstart" 
                element={
                    <ProtectedRoute>
                        <APMQuickstartPage />
                    </ProtectedRoute>
                } 
            />

            {/* Public Pricing Page — no auth */}
            <Route path="/pricing" element={<PricingPage />} />

            {/* Admin: Monetization */}
            <Route
                path="/admin/plans"
                element={
                    <ProtectedRoute>
                        <AdminPlansPage />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/admin/email-templates"
                element={
                    <ProtectedRoute>
                        <AdminEmailTemplatesPage />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/admin/leads"
                element={
                    <ProtectedRoute>
                        <AdminLeadsPage />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/admin/automation-templates"
                element={
                    <ProtectedRoute>
                        <AutomationTemplatesPage />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/admin/aws-deploy"
                element={
                    <ProtectedRoute>
                        <AWSDeployWizardPage />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/ai-monitoring"
                element={
                    <ProtectedRoute>
                        <AIMonitoringPage />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/oneagent-fleet"
                element={
                    <ProtectedRoute>
                        <OneAgentFleetPage />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/ask-falconops"
                element={
                    <ProtectedRoute>
                        <AskFalconOpsPage />
                    </ProtectedRoute>
                }
            />
            <Route
                path="/ai-observability"
                element={
                    <ProtectedRoute>
                        <AIObservabilityPage />
                    </ProtectedRoute>
                }
            />

            {/* Public portal - no auth wrapper */}
            <Route path="/portal/:token" element={<PublicPortalPage />} />
            
            {/* Catch all - redirect to landing */}
            <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
    );
};

function App() {
    return (
        <BrowserRouter>
            <ThemeProvider>
                <LanguageProvider>
                    <AuthProvider>
                        <GlobalFiltersProvider>
                            <AppRoutes />
                        </GlobalFiltersProvider>
                        <Toaster
                            position="top-right"
                            toastOptions={{
                                style: {
                                    background: 'hsl(0 0% 4%)',
                                    border: '1px solid hsl(0 0% 15%)',
                                    color: 'hsl(0 0% 98%)',
                                },
                            }}
                        />
                    </AuthProvider>
                </LanguageProvider>
            </ThemeProvider>
        </BrowserRouter>
    );
}

export default App;
