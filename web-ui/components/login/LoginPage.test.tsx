import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { LoginPage } from './LoginPage';

vi.mock('@clerk/nextjs', () => ({
  SignInButton: ({ children }: { children: React.ReactNode }) => React.createElement(React.Fragment, null, children),
}));

describe('LoginPage accessibility', () => {
  it('keeps decorative layers out of the accessibility tree', () => {
    const { container } = render(React.createElement(LoginPage));
    const contextEngineeringNote = screen.getByText('context engineering');
    const deepResearchNote = screen.getByText('DEEP RESEARCH');

    expect(screen.getByRole('button', { name: 'Log in' })).toBeInTheDocument();
    expect(contextEngineeringNote.closest('[aria-hidden="true"]')).not.toBeNull();
    expect(deepResearchNote.closest('[aria-hidden="true"]')).not.toBeNull();
    expect(container.querySelector('.svg-filters')).toHaveAttribute('aria-hidden', 'true');
    expect(container.querySelector('.drafting-layer')).toHaveAttribute('aria-hidden', 'true');
    expect(container.querySelector('.physical-tools')).toHaveAttribute('aria-hidden', 'true');
    expect(container.querySelector('.debris')).toHaveAttribute('aria-hidden', 'true');
  });
});
