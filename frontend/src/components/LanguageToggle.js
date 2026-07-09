import React from 'react';
import { useLanguage } from '../context/LanguageContext';
import { Button } from '../components/ui/button';
import { Globe } from 'lucide-react';

export const LanguageToggle = ({ variant = 'ghost', size = 'sm' }) => {
    const { language, toggleLanguage } = useLanguage();

    return (
        <Button
            variant={variant}
            size={size}
            onClick={toggleLanguage}
            className="gap-2"
            data-testid="language-toggle"
        >
            <Globe className="w-4 h-4" />
            <span className="font-medium">
                {language === 'en' ? 'العربية' : 'English'}
            </span>
        </Button>
    );
};
