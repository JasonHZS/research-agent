'use client';

import { useState, useCallback, memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import rehypeRaw from 'rehype-raw';
import { Check, Copy } from 'lucide-react';
import { cn } from '@/lib/utils';

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

// Code block with copy button
function CodeBlock({
  children,
  className,
  ...props
}: React.HTMLAttributes<HTMLElement> & { children?: React.ReactNode }) {
  const [copied, setCopied] = useState(false);
  const isInline = !className?.includes('hljs');

  const handleCopy = useCallback(async () => {
    const text = typeof children === 'string' ? children : '';
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [children]);

  if (isInline) {
    return (
      <code className={cn('bg-muted px-1.5 py-0.5 rounded text-sm font-mono', className)} {...props}>
        {children}
      </code>
    );
  }

  return (
    <div className="relative group">
      <button
        onClick={handleCopy}
        className="absolute right-2 top-2 p-1.5 rounded-md bg-background/80 opacity-0 group-hover:opacity-100 transition-opacity hover:bg-muted"
        title="Copy code"
      >
        {copied ? (
          <Check className="h-4 w-4 text-green-500" />
        ) : (
          <Copy className="h-4 w-4 text-muted-foreground" />
        )}
      </button>
      <code className={className} {...props}>
        {children}
      </code>
    </div>
  );
}

// Custom link component that opens in new tab
function CustomLink({
  href,
  children,
  ...props
}: React.AnchorHTMLAttributes<HTMLAnchorElement>) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-primary underline underline-offset-2 hover:text-primary/80"
      {...props}
    >
      {children}
    </a>
  );
}

// Custom table wrapper for horizontal scroll
function TableWrapper({ children }: { children: React.ReactNode }) {
  return (
    <div className="overflow-x-auto my-4">
      <table className="w-full border-collapse">{children}</table>
    </div>
  );
}

export const MarkdownRenderer = memo(function MarkdownRenderer({
  content,
  className,
}: MarkdownRendererProps) {
  return (
    <ReactMarkdown
      className={cn('markdown-content', className)}
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeHighlight, rehypeRaw]}
      components={{
        code: CodeBlock as any,
        a: CustomLink as any,
        table: TableWrapper as any,
        // Add horizontal rule styling
        hr: () => <hr className="border-border my-6" />,
        // Add image styling
        img: ({ src, alt, ...props }) => (
          <img
            src={src}
            alt={alt}
            className="max-w-full h-auto rounded-lg my-4"
            loading="lazy"
            {...props}
          />
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
});
