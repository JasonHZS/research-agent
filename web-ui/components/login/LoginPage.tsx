'use client';

import { SignInButton } from '@clerk/nextjs';
import './login-page.css';

export function LoginPage() {
  return (
    <div className="login-page">
      {/* SVG Filters */}
      <svg className="svg-filters" aria-hidden="true">
        <defs>
          <filter id="ink-bleed" x="-10%" y="-10%" width="120%" height="120%">
            <feTurbulence type="fractalNoise" baseFrequency="0.08" numOctaves={3} result="noise" />
            <feDisplacementMap in="SourceGraphic" in2="noise" scale={3} xChannelSelector="R" yChannelSelector="G" result="displaced" />
            <feGaussianBlur in="displaced" stdDeviation={0.8} result="blurred" />
            <feMerge>
              <feMergeNode in="blurred" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
      </svg>

      <div className="workspace">
        {/* Physical drawing tools */}
        <div className="physical-tools" aria-hidden="true">
          {/* Mechanical pencil — silver, top-left */}
          <div className="mech-pencil">
            <div className="mech-lead" />
          </div>

          {/* Black pencil — bottom-left */}
          <div className="black-pencil">
            <div className="pencil-stripe" />
            <div className="black-pencil-lead" />
          </div>

          {/* Fineliner pen — right side */}
          <div className="fineliner">
            <div className="fineliner-cap" />
            <div className="fineliner-tip" />
          </div>

          {/* Eraser */}
          <div className="eraser" />
        </div>

        {/* Pencil shavings / debris */}
        <div className="debris" aria-hidden="true">
          <div className="shaving" style={{ top: '18vh', right: '18vw', width: 4, height: 2, transform: 'rotate(45deg)' }} />
          <div className="shaving" style={{ top: '19vh', right: '16vw', width: 3, height: 3, transform: 'rotate(12deg)' }} />
          <div className="shaving" style={{ top: '14vh', right: '17vw', width: 5, height: 2, transform: 'rotate(88deg)' }} />
          <div className="shaving" style={{ top: '22vh', right: '14vw', width: 2, height: 4, transform: 'rotate(33deg)' }} />
          <div className="shaving" style={{ top: '16vh', right: '19vw', width: 6, height: 2, transform: 'rotate(-15deg)', opacity: 0.7 }} />
          {/* Pencil lead dots */}
          <div className="shaving" style={{ bottom: 120, left: 100, width: 1, height: 1, background: '#444' }} />
          <div className="shaving" style={{ bottom: 115, left: 105, width: 1.5, height: 1, background: '#444' }} />
          <div className="shaving" style={{ bottom: 125, left: 95, width: 1, height: 1, background: '#444' }} />
        </div>

        {/* Main sketch composition */}
        <div className="sketch-composition">
          {/* Drafting / construction lines */}
          <svg className="drafting-layer" viewBox="0 0 800 500" aria-hidden="true">
            {/* Vertical margin lines (dashed) */}
            <line x1="100" y1="0" x2="100" y2="500" className="draft-line-dash" />
            <line x1="700" y1="0" x2="700" y2="500" className="draft-line-dash" />

            {/* Horizontal baseline guides */}
            <line x1="50" y1="180" x2="750" y2="180" className="draft-line" />
            <line x1="50" y1="260" x2="750" y2="260" className="draft-line" />
            <line x1="50" y1="360" x2="750" y2="360" className="draft-line" />

            {/* Diagonal construction lines */}
            <line x1="150" y1="150" x2="650" y2="400" className="draft-line" style={{ opacity: 0.3 }} />
            <line x1="100" y1="250" x2="700" y2="200" className="draft-line" style={{ opacity: 0.3 }} />

            {/* Crosshair — top */}
            <path d="M 400 30 L 400 50 M 390 40 L 410 40" stroke="var(--graphite)" strokeWidth="1" fill="none" />
            {/* Crosshair — bottom */}
            <path d="M 400 450 L 400 470 M 390 460 L 410 460" stroke="var(--graphite)" strokeWidth="1" fill="none" />
            <circle cx="400" cy="40" r="6" stroke="var(--graphite)" strokeWidth="0.5" fill="none" />

            {/* Orange cross marks (left & right alignment) */}
            <path d="M 100 250 L 120 250 M 110 240 L 110 260" stroke="var(--accent-orange)" strokeWidth="1" fill="none" />
            <path d="M 700 250 L 680 250 M 690 240 L 690 260" stroke="var(--accent-orange)" strokeWidth="1" fill="none" />

            {/* Arrow annotations */}
            <path d="M 160 130 Q 180 180 200 200" stroke="var(--graphite)" strokeWidth="1" fill="none" markerEnd="url(#arrowhead)" />
            <path d="M 520 120 Q 500 160 490 200" stroke="var(--graphite)" strokeWidth="1" fill="none" markerEnd="url(#arrowhead)" />
            <path d="M 420 310 Q 450 330 480 300" stroke="var(--graphite)" strokeWidth="1" fill="none" markerEnd="url(#arrowhead)" />

            {/* Orange dashed arc + circle */}
            <path d="M 250 280 Q 400 340 550 280" stroke="var(--accent-orange)" strokeWidth="1" strokeDasharray="2 3" fill="none" />
            <circle cx="400" cy="220" r="140" stroke="var(--graphite-light)" strokeWidth="0.5" fill="none" />

            <defs>
              <marker id="arrowhead" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
                <polygon points="0 0, 6 3, 0 6" fill="var(--graphite)" />
              </marker>
            </defs>
          </svg>

          {/* Center text */}
          <div className="text-layer">
            <div className="brief-text">Deep Research Agent</div>

            <SignInButton mode="modal">
              <button className="login-link" type="button">
                Log in
              </button>
            </SignInButton>

            <div className="brief-text bottom">ArXiv · GitHub · HuggingFace · Hacker News</div>
          </div>

          {/* Annotations */}
          <div aria-hidden="true">
            <div className="annotation note-1 note-hand">context engineering</div>
            <div className="annotation note-2">
              MULTIMODAL.<br />
              <span style={{ fontSize: '8px', opacity: 0.6 }}>(REF: LANGGRAPH_V1)</span>
            </div>
            <div className="annotation note-3 note-hand">harness engineering</div>
            <div className="annotation note-4">DEEP RESEARCH</div>

            <div className="annotation" style={{ top: 80, left: 350 }}>CONTEXT WINDOW</div>
            <div className="annotation" style={{ bottom: 70, right: 120, textAlign: 'right' }}>
              ARCH: AGENT<br />
              TOOLS: 12
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
