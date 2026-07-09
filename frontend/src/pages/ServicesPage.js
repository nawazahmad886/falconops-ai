import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Button } from '../components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Badge } from '../components/ui/badge';
import { useLanguage } from '../context/LanguageContext';
import { LanguageToggle } from '../components/LanguageToggle';
import {
    Server,
    Cpu,
    Activity,
    Cloud,
    Shield,
    Zap,
    CheckCircle2,
    ArrowRight,
    Settings,
    BarChart3,
    AlertTriangle,
    Brain,
    Eye,
    Layers,
    Search,
    Globe,
} from 'lucide-react';

const monitoringPlatforms = [
    {
        id: 'solarwinds',
        name: 'SolarWinds',
        nameAr: 'سولار ويندز',
        tagline: 'Comprehensive IT Infrastructure Monitoring',
        taglineAr: 'مراقبة شاملة للبنية التحتية لتكنولوجيا المعلومات',
        description: 'End-to-end deployment, configuration, and optimization of SolarWinds Orion platform for enterprise-scale infrastructure monitoring.',
        descriptionAr: 'نشر شامل وتكوين وتحسين منصة SolarWinds Orion لمراقبة البنية التحتية على مستوى المؤسسات.',
        icon: Server,
        color: 'text-orange-500',
        bgColor: 'bg-orange-500/10',
        services: [
            'Architecture design & planning',
            'High Availability & Disaster Recovery configuration',
            'Alert engineering & threshold optimization',
            'Performance tuning & capacity planning',
            'Enterprise scaling & multi-site deployment',
            'Custom reporting & executive dashboards',
        ],
        servicesAr: [
            'تصميم وتخطيط البنية',
            'تكوين التوفر العالي واستعادة الكوارث',
            'هندسة التنبيهات وتحسين العتبات',
            'ضبط الأداء وتخطيط السعة',
            'التوسع المؤسسي والنشر متعدد المواقع',
            'التقارير المخصصة ولوحات المعلومات التنفيذية',
        ],
        images: [
            { url: 'https://documentation.solarwinds.com/en/success_center/eoc/content/resources/images/eocgettingstartedguide/eoc-dashboard-summary.png', alt: 'SolarWinds EOC Dashboard' },
            { url: 'https://cdn.mos.cms.futurecdn.net/4nATxyW9g8bjPYBqGNxQZK-1602-80.jpg', alt: 'SolarWinds Network Performance Monitor' },
        ],
    },
    {
        id: 'appdynamics',
        name: 'AppDynamics',
        nameAr: 'آب دايناميكس',
        tagline: 'Application Performance Management',
        taglineAr: 'إدارة أداء التطبيقات',
        description: 'Full-stack APM deployment with business transaction monitoring, agent configuration, and AI-powered analytics.',
        descriptionAr: 'نشر APM كامل مع مراقبة معاملات الأعمال وتكوين الوكيل والتحليلات المدعومة بالذكاء الاصطناعي.',
        icon: Activity,
        color: 'text-blue-500',
        bgColor: 'bg-blue-500/10',
        services: [
            'Controller installation & configuration',
            'Agent deployment (Java, .NET, NodeJS, PHP)',
            'Business transaction design & optimization',
            'Health rule engineering & baseline tuning',
            'End User Monitoring (EUM) setup',
            'Synthetic monitoring configuration',
        ],
        servicesAr: [
            'تثبيت وتكوين المتحكم',
            'نشر الوكيل (Java, .NET, NodeJS, PHP)',
            'تصميم وتحسين معاملات الأعمال',
            'هندسة قواعد الصحة وضبط خط الأساس',
            'إعداد مراقبة المستخدم النهائي (EUM)',
            'تكوين المراقبة الاصطناعية',
        ],
        images: [
            { url: 'https://appd-modernization.awsworkshop.io/images/mobilize/biz_txns_01.png', alt: 'AppDynamics Business Transactions' },
            { url: 'https://www.wwt.com/api-new/attachments/5f47fef98220530082415b87/thumbnail?width=1200', alt: 'AppDynamics Flow Map' },
        ],
    },
    {
        id: 'dynatrace',
        name: 'Dynatrace',
        nameAr: 'داينا تريس',
        tagline: 'AI-Powered Full Stack Observability',
        taglineAr: 'قابلية المراقبة الكاملة المدعومة بالذكاء الاصطناعي',
        description: 'OneAgent deployment with Davis AI configuration for automatic root cause analysis and cloud-native monitoring.',
        descriptionAr: 'نشر OneAgent مع تكوين Davis AI لتحليل السبب الجذري التلقائي ومراقبة السحابة الأصلية.',
        icon: Brain,
        color: 'text-green-500',
        bgColor: 'bg-green-500/10',
        services: [
            'OneAgent deployment & configuration',
            'Davis AI root cause configuration',
            'Cloud-native monitoring (AWS, Azure, GCP)',
            'Kubernetes & container observability',
            'Real User Monitoring setup',
            'Custom metrics & extensions',
        ],
        servicesAr: [
            'نشر وتكوين OneAgent',
            'تكوين تحليل السبب الجذري Davis AI',
            'المراقبة السحابية الأصلية (AWS, Azure, GCP)',
            'مراقبة Kubernetes والحاويات',
            'إعداد مراقبة المستخدم الحقيقي',
            'المقاييس المخصصة والإضافات',
        ],
        images: [
            { url: 'https://dt-cdn.net/images/smartscape-inter1-1687-680a65579e.png', alt: 'Dynatrace Smartscape' },
            { url: 'https://cdn.dm.dynatrace.com/assets/Marketing/screenshots/dynatrace-dashboard.png', alt: 'Dynatrace Dashboard' },
        ],
    },
    {
        id: 'elastic',
        name: 'Elastic Stack',
        nameAr: 'إلاستيك ستاك',
        tagline: 'Search, Observe, Protect',
        taglineAr: 'البحث، المراقبة، الحماية',
        description: 'Complete ELK Stack deployment for log management, APM, security analytics, and enterprise search capabilities.',
        descriptionAr: 'نشر كامل لـ ELK Stack لإدارة السجلات وAPM وتحليلات الأمان وقدرات البحث المؤسسي.',
        icon: Search,
        color: 'text-yellow-500',
        bgColor: 'bg-yellow-500/10',
        services: [
            'Elasticsearch cluster deployment & scaling',
            'Logstash pipeline configuration',
            'Kibana dashboards & visualizations',
            'Elastic APM integration',
            'Security (SIEM) configuration',
            'Index lifecycle management & optimization',
        ],
        servicesAr: [
            'نشر وتوسيع مجموعة Elasticsearch',
            'تكوين خطوط أنابيب Logstash',
            'لوحات معلومات Kibana والتصورات',
            'تكامل Elastic APM',
            'تكوين الأمان (SIEM)',
            'إدارة دورة حياة الفهرس والتحسين',
        ],
        images: [
            { url: 'https://images.contentstack.io/v3/assets/bltefdd0b53724fa2ce/blt5dd97add8d8d3e4a/5d0d5765c73d3c5d5a5d74e5/screenshot-dashboard-logs-720x420.png', alt: 'Elastic Kibana Dashboard' },
            { url: 'https://images.contentstack.io/v3/assets/bltefdd0b53724fa2ce/bltf71eadef2d6f6b93/64d110dfe377051e39eb6e82/screenshot-apm-services-720x420.png', alt: 'Elastic APM' },
        ],
    },
    {
        id: 'site24x7',
        name: 'Site24x7',
        nameAr: 'سايت 24×7',
        tagline: 'All-in-One Monitoring Solution',
        taglineAr: 'حل مراقبة شامل',
        description: 'Cloud-based monitoring for websites, servers, applications, and cloud infrastructure with real user monitoring.',
        descriptionAr: 'مراقبة سحابية للمواقع والخوادم والتطبيقات والبنية التحتية السحابية مع مراقبة المستخدم الحقيقي.',
        icon: Globe,
        color: 'text-purple-500',
        bgColor: 'bg-purple-500/10',
        services: [
            'Website & URL monitoring setup',
            'Server monitoring agent deployment',
            'Application Performance Monitoring (APM)',
            'Cloud infrastructure monitoring (AWS, Azure)',
            'Real User Monitoring (RUM) configuration',
            'Custom alert thresholds & integrations',
        ],
        servicesAr: [
            'إعداد مراقبة المواقع وعناوين URL',
            'نشر وكيل مراقبة الخادم',
            'مراقبة أداء التطبيقات (APM)',
            'مراقبة البنية التحتية السحابية (AWS, Azure)',
            'تكوين مراقبة المستخدم الحقيقي (RUM)',
            'عتبات التنبيه المخصصة والتكاملات',
        ],
        images: [
            { url: 'https://www.site24x7.com/images/homepage-images/it-monitoring-reimagined-hero-image.svg', alt: 'Site24x7 Dashboard' },
            { url: 'https://www.site24x7.com/help/images/apm-insight-overview.png', alt: 'Site24x7 APM' },
        ],
    },
];

const additionalServices = [
    {
        icon: Eye,
        title: 'Monitoring Health Audit',
        description: 'Comprehensive assessment of your current monitoring environment with optimization roadmap.',
        features: ['Alert accuracy analysis', 'False positive ratio review', 'Health rule design audit', 'Architecture gap assessment', 'MTTR trend analysis'],
    },
    {
        icon: Shield,
        title: 'Managed Monitoring',
        description: 'AI-enhanced managed monitoring services with continuous optimization.',
        features: ['24/7 alert management', 'Agent lifecycle management', 'Monthly performance reviews', 'AI summary reports', 'Continuous tuning'],
    },
    {
        icon: Zap,
        title: 'AI Automation Layer',
        description: 'Our proprietary AI platform for intelligent alert correlation and automation.',
        features: ['Intelligent alert correlation', 'Up to 70% noise reduction', 'Root cause identification', 'Incident summary generation', 'NOC Copilot assistance'],
    },
];

export const ServicesPage = () => {
    const [selectedPlatform, setSelectedPlatform] = useState('solarwinds');
    const { language, isRTL } = useLanguage();

    return (
        <div className={`min-h-screen bg-background noise ${isRTL ? 'rtl' : 'ltr'}`}>
            {/* Navigation */}
            <header className="fixed top-0 left-0 right-0 z-50 glass-strong">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex items-center justify-between h-16">
                        <Link to="/" className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
                                <span className="text-primary font-heading font-bold text-xl">F</span>
                            </div>
                            <span className="font-heading font-semibold text-xl tracking-tight">
                                FALCON<span className="text-primary">APPS</span>
                            </span>
                        </Link>
                        <nav className="hidden md:flex items-center gap-6">
                            <Link to="/about" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                                {language === 'ar' ? 'من نحن' : 'About'}
                            </Link>
                            <Link to="/services" className="text-sm text-primary font-medium">
                                {language === 'ar' ? 'الخدمات' : 'Services'}
                            </Link>
                            <Link to="/training" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                                {language === 'ar' ? 'التدريب' : 'Training'}
                            </Link>
                            <Link to="/login" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
                                {language === 'ar' ? 'تسجيل الدخول' : 'Login'}
                            </Link>
                            <LanguageToggle />
                            <Button asChild size="sm">
                                <Link to="/contact">{language === 'ar' ? 'اتصل بنا' : 'Contact Us'}</Link>
                            </Button>
                        </nav>
                    </div>
                </div>
            </header>

            {/* Hero Section */}
            <section className="relative pt-32 pb-16 px-4 sm:px-6 lg:px-8">
                <div className="absolute inset-0 grid-pattern opacity-20" />
                <div className="relative max-w-7xl mx-auto text-center">
                    <motion.div
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ duration: 0.6 }}
                    >
                        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 text-primary text-sm font-medium mb-6">
                            <Layers className="w-4 h-4" />
                            {language === 'ar' ? 'خدمات مراقبة المؤسسات' : 'Enterprise Monitoring Services'}
                        </div>
                        <h1 className="font-heading font-bold text-4xl sm:text-5xl lg:text-6xl tracking-tight mb-6 uppercase">
                            {language === 'ar' ? 'حزمة المراقبة' : 'Monitoring Stack'}
                            <br />
                            <span className="text-primary">{language === 'ar' ? 'النشر والتحسين' : 'Deployment & Optimization'}</span>
                        </h1>
                        <p className="text-lg text-muted-foreground max-w-3xl mx-auto mb-8">
                            {language === 'ar' 
                                ? 'نشر احترافي وتكوين وتحسين منصات مراقبة المؤسسات. من تصميم البنية إلى الأتمتة المدعومة بالذكاء الاصطناعي.'
                                : 'Expert deployment, configuration, and optimization of enterprise monitoring platforms. From architecture design to AI-powered automation.'}
                        </p>
                    </motion.div>
                </div>
            </section>

            {/* Platform Tabs */}
            <section className="py-12 px-4 sm:px-6 lg:px-8">
                <div className="max-w-7xl mx-auto">
                    <h2 className="font-heading font-semibold text-2xl md:text-3xl mb-8 text-center">
                        {language === 'ar' ? 'نشر مراقبة المؤسسات' : 'Enterprise Monitoring Deployment'}
                    </h2>
                    
                    <Tabs value={selectedPlatform} onValueChange={setSelectedPlatform} className="space-y-8">
                        <TabsList className="w-full max-w-3xl mx-auto grid grid-cols-5 bg-muted/30 border border-border/40">
                            {monitoringPlatforms.map((platform) => (
                                <TabsTrigger 
                                    key={platform.id} 
                                    value={platform.id}
                                    className="data-[state=active]:bg-primary/10 text-xs sm:text-sm"
                                    data-testid={`tab-${platform.id}`}
                                >
                                    {language === 'ar' ? platform.nameAr : platform.name}
                                </TabsTrigger>
                            ))}
                        </TabsList>

                        {monitoringPlatforms.map((platform) => {
                            const Icon = platform.icon;
                            return (
                                <TabsContent key={platform.id} value={platform.id}>
                                    <motion.div
                                        initial={{ opacity: 0, y: 10 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        transition={{ duration: 0.3 }}
                                    >
                                        <Card className="bg-card/50 border-border/40">
                                            <CardHeader>
                                                <div className="flex items-center gap-4">
                                                    <div className={`w-14 h-14 rounded-xl ${platform.bgColor} flex items-center justify-center`}>
                                                        <Icon className={`w-7 h-7 ${platform.color}`} />
                                                    </div>
                                                    <div>
                                                        <CardTitle className="font-heading text-2xl">
                                                            {language === 'ar' ? platform.nameAr : platform.name}
                                                        </CardTitle>
                                                        <CardDescription>
                                                            {language === 'ar' ? platform.taglineAr : platform.tagline}
                                                        </CardDescription>
                                                    </div>
                                                </div>
                                            </CardHeader>
                                            <CardContent className="space-y-8">
                                                <p className="text-muted-foreground">
                                                    {language === 'ar' ? platform.descriptionAr : platform.description}
                                                </p>
                                                
                                                {/* Services Grid */}
                                                <div>
                                                    <h4 className="font-heading font-medium text-lg mb-4">
                                                        {language === 'ar' ? 'خدماتنا' : 'Our Services'}
                                                    </h4>
                                                    <div className="grid md:grid-cols-2 gap-3">
                                                        {(language === 'ar' ? platform.servicesAr : platform.services).map((service, idx) => (
                                                            <div key={idx} className="flex items-start gap-2 p-3 rounded-lg bg-muted/30">
                                                                <CheckCircle2 className="w-5 h-5 text-primary shrink-0 mt-0.5" />
                                                                <span className="text-sm">{service}</span>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>

                                                {/* Screenshots */}
                                                <div>
                                                    <h4 className="font-heading font-medium text-lg mb-4">
                                                        {language === 'ar' ? 'قدرات المنصة' : 'Platform Capabilities'}
                                                    </h4>
                                                    <div className="grid md:grid-cols-2 gap-4">
                                                        {platform.images.map((image, idx) => (
                                                            <div key={idx} className="relative group overflow-hidden rounded-lg border border-border/40">
                                                                <img 
                                                                    src={image.url} 
                                                                    alt={image.alt}
                                                                    className="w-full h-48 object-cover object-top transition-transform group-hover:scale-105"
                                                                    onError={(e) => {
                                                                        e.target.src = 'https://images.unsplash.com/photo-1680992046626-418f7e910589?w=800&q=80';
                                                                    }}
                                                                />
                                                                <div className="absolute inset-0 bg-gradient-to-t from-background/80 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-end p-4">
                                                                    <p className="text-sm font-medium">{image.alt}</p>
                                                                </div>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>

                                                <div className="flex items-center gap-4 pt-4">
                                                    <Button asChild>
                                                        <Link to="/contact">
                                                            {language === 'ar' ? `طلب نشر ${platform.nameAr}` : `Request ${platform.name} Deployment`}
                                                            <ArrowRight className={`w-4 h-4 ${isRTL ? 'mr-2 rotate-180' : 'ml-2'}`} />
                                                        </Link>
                                                    </Button>
                                                    <Button variant="outline" asChild>
                                                        <Link to="/training">
                                                            {language === 'ar' ? 'عرض خيارات التدريب' : 'View Training Options'}
                                                        </Link>
                                                    </Button>
                                                </div>
                                            </CardContent>
                                        </Card>
                                    </motion.div>
                                </TabsContent>
                            );
                        })}
                    </Tabs>
                </div>
            </section>

            {/* Additional Services */}
            <section className="py-20 px-4 sm:px-6 lg:px-8 bg-muted/30">
                <div className="max-w-7xl mx-auto">
                    <div className="text-center mb-12">
                        <h2 className="font-heading font-semibold text-2xl md:text-3xl mb-4">
                            Beyond Monitoring. Into Automation.
                        </h2>
                        <p className="text-muted-foreground max-w-2xl mx-auto">
                            Comprehensive services to transform your IT operations
                        </p>
                    </div>

                    <div className="grid md:grid-cols-3 gap-6">
                        {additionalServices.map((service, idx) => {
                            const Icon = service.icon;
                            return (
                                <motion.div
                                    key={idx}
                                    initial={{ opacity: 0, y: 20 }}
                                    whileInView={{ opacity: 1, y: 0 }}
                                    transition={{ duration: 0.4, delay: idx * 0.1 }}
                                    viewport={{ once: true }}
                                >
                                    <Card className="h-full bg-card/50 border-border/40 hover:border-primary/50 transition-colors">
                                        <CardContent className="p-6">
                                            <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                                                <Icon className="w-6 h-6 text-primary" />
                                            </div>
                                            <h3 className="font-heading font-medium text-xl mb-2">{service.title}</h3>
                                            <p className="text-sm text-muted-foreground mb-4">{service.description}</p>
                                            <ul className="space-y-2">
                                                {service.features.map((feature, fIdx) => (
                                                    <li key={fIdx} className="flex items-center gap-2 text-sm">
                                                        <CheckCircle2 className="w-4 h-4 text-primary shrink-0" />
                                                        <span className="text-muted-foreground">{feature}</span>
                                                    </li>
                                                ))}
                                            </ul>
                                        </CardContent>
                                    </Card>
                                </motion.div>
                            );
                        })}
                    </div>
                </div>
            </section>

            {/* Process Section */}
            <section className="py-20 px-4 sm:px-6 lg:px-8">
                <div className="max-w-7xl mx-auto">
                    <div className="text-center mb-12">
                        <h2 className="font-heading font-semibold text-2xl md:text-3xl mb-4">
                            Our Deployment Process
                        </h2>
                    </div>
                    <div className="grid md:grid-cols-4 gap-8">
                        {[
                            { step: '01', title: 'Discovery', desc: 'Assess your environment, requirements, and integration needs' },
                            { step: '02', title: 'Architecture', desc: 'Design scalable, enterprise-grade monitoring architecture' },
                            { step: '03', title: 'Deployment', desc: 'Professional installation with best practices' },
                            { step: '04', title: 'Optimization', desc: 'Fine-tune alerts, dashboards, and automation' },
                        ].map((item, idx) => (
                            <motion.div
                                key={idx}
                                initial={{ opacity: 0, x: -20 }}
                                whileInView={{ opacity: 1, x: 0 }}
                                transition={{ duration: 0.4, delay: idx * 0.1 }}
                                viewport={{ once: true }}
                                className="relative"
                            >
                                <div className="font-heading font-bold text-6xl text-primary/10 absolute -top-4 -left-2">
                                    {item.step}
                                </div>
                                <div className="relative pt-8">
                                    <h3 className="font-heading font-medium text-xl mb-2">{item.title}</h3>
                                    <p className="text-sm text-muted-foreground">{item.desc}</p>
                                </div>
                            </motion.div>
                        ))}
                    </div>
                </div>
            </section>

            {/* CTA */}
            <section className="py-20 px-4 sm:px-6 lg:px-8">
                <div className="max-w-4xl mx-auto text-center">
                    <Card className="bg-primary/5 border-primary/20 p-8 sm:p-12">
                        <CardContent className="p-0">
                            <h2 className="font-heading font-semibold text-3xl md:text-4xl mb-4">
                                Ready to Optimize Your Monitoring?
                            </h2>
                            <p className="text-muted-foreground mb-8 max-w-xl mx-auto">
                                Get a free monitoring health assessment and discover how we can 
                                reduce your alert noise and improve MTTR.
                            </p>
                            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
                                <Button asChild size="lg" className="glow-primary">
                                    <Link to="/contact">
                                        Request Free Assessment
                                        <ArrowRight className="w-5 h-5 ml-2" />
                                    </Link>
                                </Button>
                                <Button variant="outline" size="lg" asChild>
                                    <Link to="/training">View Training Programs</Link>
                                </Button>
                            </div>
                        </CardContent>
                    </Card>
                </div>
            </section>

            {/* Footer */}
            <footer className="border-t border-border/40 py-12 px-4 sm:px-6 lg:px-8">
                <div className="max-w-7xl mx-auto">
                    <div className="flex flex-col md:flex-row items-center justify-between gap-4">
                        <div className="flex items-center gap-3">
                            <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center">
                                <span className="text-primary font-heading font-bold">F</span>
                            </div>
                            <span className="font-heading font-semibold tracking-tight">
                                FALCON<span className="text-primary">APPS</span>
                            </span>
                        </div>
                        <p className="text-sm text-muted-foreground">
                            © 2025 FalconOps AI. Engineering Proactive IT Ecosystems.
                        </p>
                    </div>
                </div>
            </footer>
        </div>
    );
};
