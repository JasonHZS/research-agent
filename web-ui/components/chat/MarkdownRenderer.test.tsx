import React from 'react';
import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { MarkdownRenderer } from './MarkdownRenderer';

describe('MarkdownRenderer math support', () => {
  it('renders inline math with KaTeX', () => {
    const { container } = render(React.createElement(MarkdownRenderer, { content: '行内公式 $E=mc^2$' }));

    expect(container.querySelector('.katex')).toBeTruthy();
    expect(
      container.querySelector('annotation[encoding="application/x-tex"]')?.textContent
    ).toContain('E=mc^2');
  });

  it('renders block math with KaTeX display mode', () => {
    const { container } = render(
      React.createElement(MarkdownRenderer, {
        content: '$$\n\\int_a^b f(x)\\,dx\n$$',
      })
    );

    expect(container.querySelector('.katex-display')).toBeTruthy();
    expect(
      container.querySelector('annotation[encoding="application/x-tex"]')?.textContent
    ).toContain('\\int_a^b f(x)\\,dx');
  });
});
