import React, { createContext, useContext, useState, useEffect } from 'react';

const translations = {
    en: {
        // Navigation
        nav: {
            about: 'About',
            services: 'Services',
            aiPlatform: 'AI Platform',
            security: 'Security',
            training: 'Training',
            login: 'Login',
            getStarted: 'Get Started',
            dashboard: 'Dashboard',
            alerts: 'Alerts',
            incidents: 'Incidents',
            runbooks: 'Runbooks',
            analytics: 'Analytics',
            settings: 'Settings',
            logout: 'Logout',
            contact: 'Contact Us',
        },
        // Landing Page
        landing: {
            badge: 'AI-Powered NOC Intelligence',
            headline1: 'Reduce Alert Noise by',
            headline2: 'Accelerate MTTR by',
            description: 'AI-driven alert correlation, root cause analysis, and autonomous operational intelligence for enterprise monitoring. Transform reactive NOC into proactive operations.',
            startTrial: 'Start Free Trial',
            seeHow: 'See How It Works',
            enterpriseSecurity: 'Enterprise Security',
            aiMonitoring: '24/7 AI Monitoring',
            noiseReduction: 'Noise Reduction',
            fasterMTTR: 'Faster MTTR',
            slaCompliance: 'SLA Compliance',
            features: 'Enterprise-Grade Intelligence',
            featuresDesc: 'Built for NOC teams who demand reliability, speed, and actionable insights.',
            pricing: 'Simple, Transparent Pricing',
            pricingDesc: 'Start with a 14-day free trial. No credit card required.',
            cta: 'Ready to Transform Your NOC?',
            ctaDesc: 'Join enterprise teams across Saudi Arabia and GCC who trust FalconOps AI for intelligent incident management.',
        },
        // Services
        services: {
            title: 'Monitoring Stack',
            subtitle: 'Deployment & Optimization',
            description: 'Expert deployment, configuration, and optimization of enterprise monitoring platforms. From architecture design to AI-powered automation.',
            solarwinds: {
                name: 'SolarWinds',
                tagline: 'Comprehensive IT Infrastructure Monitoring',
                description: 'End-to-end deployment, configuration, and optimization of SolarWinds Orion platform for enterprise-scale infrastructure monitoring.',
            },
            appdynamics: {
                name: 'AppDynamics',
                tagline: 'Application Performance Management',
                description: 'Full-stack APM deployment with business transaction monitoring, agent configuration, and AI-powered analytics.',
            },
            dynatrace: {
                name: 'Dynatrace',
                tagline: 'AI-Powered Full Stack Observability',
                description: 'OneAgent deployment with Davis AI configuration for automatic root cause analysis and cloud-native monitoring.',
            },
            elastic: {
                name: 'Elastic Stack',
                tagline: 'Search, Observe, Protect',
                description: 'Complete ELK Stack deployment for log management, APM, security analytics, and enterprise search capabilities.',
            },
            site24x7: {
                name: 'Site24x7',
                tagline: 'All-in-One Monitoring Solution',
                description: 'Cloud-based monitoring for websites, servers, applications, and cloud infrastructure with real user monitoring.',
            },
            requestDeployment: 'Request Deployment',
            viewTraining: 'View Training Options',
        },
        // Dashboard
        dashboard: {
            title: 'Dashboard',
            subtitle: 'Real-time NOC intelligence overview',
            openAlerts: 'Open Alerts',
            openIncidents: 'Open Incidents',
            avgMTTR: 'Avg MTTR',
            slaCompliance: 'SLA Compliance',
            refresh: 'Refresh',
            incidentsTrend: 'Incidents Trend (7 Days)',
            alertsBySeverity: 'Alerts by Severity',
            serviceHealth: 'Service Health',
            recentIncidents: 'Recent Incidents',
            recentAlerts: 'Recent Alerts',
            viewAll: 'View All',
            noAlerts: 'No alerts yet',
            noIncidents: 'No incidents',
            allOperational: 'All systems operational',
        },
        // Common
        common: {
            loading: 'Loading...',
            error: 'Error',
            success: 'Success',
            cancel: 'Cancel',
            save: 'Save',
            delete: 'Delete',
            edit: 'Edit',
            create: 'Create',
            search: 'Search',
            filter: 'Filter',
            clear: 'Clear',
            submit: 'Submit',
            close: 'Close',
            back: 'Back',
            next: 'Next',
            previous: 'Previous',
            yes: 'Yes',
            no: 'No',
            all: 'All',
            none: 'None',
            status: 'Status',
            severity: 'Severity',
            critical: 'Critical',
            warning: 'Warning',
            info: 'Info',
            open: 'Open',
            resolved: 'Resolved',
            acknowledged: 'Acknowledged',
        },
        // Auth
        auth: {
            welcomeBack: 'Welcome Back',
            signIn: 'Sign in to your FalconOps AI account',
            createAccount: 'Create Account',
            startTrial: 'Start your 14-day free trial',
            email: 'Email',
            password: 'Password',
            fullName: 'Full Name',
            organization: 'Organization',
            signInBtn: 'Sign In',
            createBtn: 'Create Account',
            noAccount: "Don't have an account?",
            haveAccount: 'Already have an account?',
            signUp: 'Sign up',
        },
        // Footer
        footer: {
            copyright: '© 2025 FalconOps AI. AI-Powered Incident Intelligence.',
        },
    },
    ar: {
        // Navigation
        nav: {
            about: 'من نحن',
            services: 'الخدمات',
            aiPlatform: 'منصة الذكاء الاصطناعي',
            security: 'الأمان',
            training: 'التدريب',
            login: 'تسجيل الدخول',
            getStarted: 'ابدأ الآن',
            dashboard: 'لوحة التحكم',
            alerts: 'التنبيهات',
            incidents: 'الحوادث',
            runbooks: 'كتب التشغيل',
            analytics: 'التحليلات',
            settings: 'الإعدادات',
            logout: 'تسجيل الخروج',
            contact: 'اتصل بنا',
        },
        // Landing Page
        landing: {
            badge: 'ذكاء اصطناعي لمركز العمليات',
            headline1: 'تقليل ضوضاء التنبيهات بنسبة',
            headline2: 'تسريع وقت الحل بنسبة',
            description: 'ربط التنبيهات المدعوم بالذكاء الاصطناعي، وتحليل السبب الجذري، والذكاء التشغيلي المستقل لمراقبة المؤسسات. حوّل مركز العمليات من ردة الفعل إلى الاستباقية.',
            startTrial: 'ابدأ التجربة المجانية',
            seeHow: 'شاهد كيف يعمل',
            enterpriseSecurity: 'أمان المؤسسات',
            aiMonitoring: 'مراقبة الذكاء الاصطناعي على مدار الساعة',
            noiseReduction: 'تقليل الضوضاء',
            fasterMTTR: 'وقت حل أسرع',
            slaCompliance: 'الامتثال لاتفاقية مستوى الخدمة',
            features: 'ذكاء على مستوى المؤسسات',
            featuresDesc: 'مصمم لفرق مركز العمليات التي تتطلب الموثوقية والسرعة والرؤى القابلة للتنفيذ.',
            pricing: 'أسعار بسيطة وشفافة',
            pricingDesc: 'ابدأ بتجربة مجانية لمدة 14 يومًا. لا حاجة لبطاقة ائتمان.',
            cta: 'هل أنت مستعد لتحويل مركز العمليات الخاص بك؟',
            ctaDesc: 'انضم إلى فرق المؤسسات في المملكة العربية السعودية ودول الخليج الذين يثقون في FalconOps AI لإدارة الحوادث الذكية.',
        },
        // Services
        services: {
            title: 'حزمة المراقبة',
            subtitle: 'النشر والتحسين',
            description: 'نشر احترافي وتكوين وتحسين منصات مراقبة المؤسسات. من تصميم البنية إلى الأتمتة المدعومة بالذكاء الاصطناعي.',
            solarwinds: {
                name: 'سولار ويندز',
                tagline: 'مراقبة شاملة للبنية التحتية لتكنولوجيا المعلومات',
                description: 'نشر شامل وتكوين وتحسين منصة SolarWinds Orion لمراقبة البنية التحتية على مستوى المؤسسات.',
            },
            appdynamics: {
                name: 'آب دايناميكس',
                tagline: 'إدارة أداء التطبيقات',
                description: 'نشر APM كامل مع مراقبة معاملات الأعمال وتكوين الوكيل والتحليلات المدعومة بالذكاء الاصطناعي.',
            },
            dynatrace: {
                name: 'داينا تريس',
                tagline: 'قابلية المراقبة الكاملة المدعومة بالذكاء الاصطناعي',
                description: 'نشر OneAgent مع تكوين Davis AI لتحليل السبب الجذري التلقائي ومراقبة السحابة الأصلية.',
            },
            elastic: {
                name: 'إلاستيك ستاك',
                tagline: 'البحث، المراقبة، الحماية',
                description: 'نشر كامل لـ ELK Stack لإدارة السجلات وAPM وتحليلات الأمان وقدرات البحث المؤسسي.',
            },
            site24x7: {
                name: 'سايت 24×7',
                tagline: 'حل مراقبة شامل',
                description: 'مراقبة سحابية للمواقع والخوادم والتطبيقات والبنية التحتية السحابية مع مراقبة المستخدم الحقيقي.',
            },
            requestDeployment: 'طلب النشر',
            viewTraining: 'عرض خيارات التدريب',
        },
        // Dashboard
        dashboard: {
            title: 'لوحة التحكم',
            subtitle: 'نظرة عامة على ذكاء مركز العمليات في الوقت الفعلي',
            openAlerts: 'التنبيهات المفتوحة',
            openIncidents: 'الحوادث المفتوحة',
            avgMTTR: 'متوسط وقت الحل',
            slaCompliance: 'الامتثال لاتفاقية مستوى الخدمة',
            refresh: 'تحديث',
            incidentsTrend: 'اتجاه الحوادث (7 أيام)',
            alertsBySeverity: 'التنبيهات حسب الخطورة',
            serviceHealth: 'صحة الخدمة',
            recentIncidents: 'الحوادث الأخيرة',
            recentAlerts: 'التنبيهات الأخيرة',
            viewAll: 'عرض الكل',
            noAlerts: 'لا توجد تنبيهات بعد',
            noIncidents: 'لا توجد حوادث',
            allOperational: 'جميع الأنظمة تعمل',
        },
        // Common
        common: {
            loading: 'جاري التحميل...',
            error: 'خطأ',
            success: 'نجاح',
            cancel: 'إلغاء',
            save: 'حفظ',
            delete: 'حذف',
            edit: 'تعديل',
            create: 'إنشاء',
            search: 'بحث',
            filter: 'تصفية',
            clear: 'مسح',
            submit: 'إرسال',
            close: 'إغلاق',
            back: 'رجوع',
            next: 'التالي',
            previous: 'السابق',
            yes: 'نعم',
            no: 'لا',
            all: 'الكل',
            none: 'لا شيء',
            status: 'الحالة',
            severity: 'الخطورة',
            critical: 'حرج',
            warning: 'تحذير',
            info: 'معلومات',
            open: 'مفتوح',
            resolved: 'تم الحل',
            acknowledged: 'تم الإقرار',
        },
        // Auth
        auth: {
            welcomeBack: 'مرحبًا بعودتك',
            signIn: 'سجل الدخول إلى حساب FalconOps AI الخاص بك',
            createAccount: 'إنشاء حساب',
            startTrial: 'ابدأ تجربتك المجانية لمدة 14 يومًا',
            email: 'البريد الإلكتروني',
            password: 'كلمة المرور',
            fullName: 'الاسم الكامل',
            organization: 'المؤسسة',
            signInBtn: 'تسجيل الدخول',
            createBtn: 'إنشاء حساب',
            noAccount: 'ليس لديك حساب؟',
            haveAccount: 'لديك حساب بالفعل؟',
            signUp: 'سجل الآن',
        },
        // Footer
        footer: {
            copyright: '© 2025 فالكون آبس. ذكاء الحوادث المدعوم بالذكاء الاصطناعي.',
        },
    },
};

const LanguageContext = createContext(null);

export const useLanguage = () => {
    const context = useContext(LanguageContext);
    if (!context) {
        throw new Error('useLanguage must be used within a LanguageProvider');
    }
    return context;
};

export const LanguageProvider = ({ children }) => {
    const [language, setLanguage] = useState(() => {
        return localStorage.getItem('falconLanguage') || 'en';
    });

    useEffect(() => {
        localStorage.setItem('falconLanguage', language);
        document.documentElement.dir = language === 'ar' ? 'rtl' : 'ltr';
        document.documentElement.lang = language;
    }, [language]);

    const t = (key) => {
        const keys = key.split('.');
        let value = translations[language];
        for (const k of keys) {
            value = value?.[k];
        }
        return value || key;
    };

    const toggleLanguage = () => {
        setLanguage(prev => prev === 'en' ? 'ar' : 'en');
    };

    const value = {
        language,
        setLanguage,
        toggleLanguage,
        t,
        isRTL: language === 'ar',
    };

    return (
        <LanguageContext.Provider value={value}>
            {children}
        </LanguageContext.Provider>
    );
};
