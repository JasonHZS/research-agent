'use client';

import { useEffect, useRef } from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { MessageBubble, StreamingMessageBubble } from './MessageBubble';
import { useChatStore } from '@/hooks/useChat';
import { cn } from '@/lib/utils';

interface MessageListProps {
  className?: string;
}

export function MessageList({ className }: MessageListProps) {
  const { currentMessages, streamingMessage } = useChatStore();
  const scrollRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [currentMessages, streamingMessage?.content]);

  const hasMessages = currentMessages.length > 0 || streamingMessage;

  return (
    <ScrollArea className={cn('flex-1', className)}>
      <div ref={containerRef} className="p-4 md:p-6 max-w-5xl mx-auto">
        {!hasMessages && (
          <div className="flex flex-col items-center justify-center min-h-[50vh] text-center">
            <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mb-4">
              <svg
                className="w-8 h-8 text-primary"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                />
              </svg>
            </div>
            <h2 className="text-xl font-semibold mb-2">Start a conversation</h2>
            <p className="text-muted-foreground max-w-md">
              Ask me about AI research, recent papers, tech trends, or anything else you'd like to explore.
            </p>
          </div>
        )}

        {hasMessages && (
          <div className="space-y-6">
            {/* Rendered messages */}
            {currentMessages.map((message) => (
              <MessageBubble key={message.id} message={message} />
            ))}

            {/* Streaming message */}
            {streamingMessage && (
              <StreamingMessageBubble
                content={streamingMessage.content}
                toolCalls={streamingMessage.toolCalls}
                thinkingContent={streamingMessage.thinkingContent}
              />
            )}

            {/* Scroll anchor */}
            <div ref={scrollRef} className="h-1" />
          </div>
        )}
      </div>
    </ScrollArea>
  );
}
