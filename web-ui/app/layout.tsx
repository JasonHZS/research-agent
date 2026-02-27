import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { ClerkProvider } from '@clerk/nextjs';
import './globals.css';
import 'highlight.js/styles/github-dark.css';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'Research Agent',
  description: 'AI-powered deep research assistant',
};

// Script to initialize theme before hydration
const themeScript = `
  (function() {
    try {
      const theme = localStorage.getItem('theme');
      if (theme === 'dark' || (!theme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
        document.documentElement.classList.add('dark');
      }
    } catch (e) {}
  })();
`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ClerkProvider>
      <html lang="en" suppressHydrationWarning>
        <head>
          <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        </head>
        <body className={inter.className}>
          <div className="flex h-screen overflow-hidden bg-background">
            {children}
          </div>
        </body>
      </html>
    </ClerkProvider>
  );
}
