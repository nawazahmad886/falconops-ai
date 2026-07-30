import React from 'react';
import { render, screen } from '@testing-library/react';
import { FalconLogo, FalconLogoFull, FalconLogoCompact } from './FalconLogo';

// Deliberately minimal — this suite exists to prove the Jest/RTL pipeline
// itself works end-to-end in CI (see the "CI never runs frontend tests"
// production-readiness finding), not to fully cover FalconLogo. Pick a
// component with zero API/context/router dependencies so this test can never
// fail for reasons unrelated to the test runner itself.

describe('FalconLogo', () => {
    it('renders an svg with the requested size', () => {
        const { container } = render(<FalconLogo size={48} />);
        const svg = container.querySelector('svg');
        expect(svg).toBeInTheDocument();
        expect(svg).toHaveAttribute('width', '48');
        expect(svg).toHaveAttribute('height', '48');
    });

    it('renders the default size when none is provided', () => {
        const { container } = render(<FalconLogo />);
        const svg = container.querySelector('svg');
        expect(svg).toHaveAttribute('width', '40');
    });
});

describe('FalconLogoFull', () => {
    it('renders the FALCONOPS AI wordmark alongside the icon', () => {
        render(<FalconLogoFull />);
        expect(screen.getByText('FALCON')).toBeInTheDocument();
        expect(screen.getByText('OPS')).toBeInTheDocument();
        expect(screen.getByText('AI')).toBeInTheDocument();
    });
});

describe('FalconLogoCompact', () => {
    it('renders without crashing', () => {
        const { container } = render(<FalconLogoCompact size={24} />);
        expect(container.querySelector('svg')).toBeInTheDocument();
    });
});
