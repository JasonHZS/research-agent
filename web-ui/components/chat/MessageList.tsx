'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { ArrowDown } from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Button } from '@/components/ui/button';
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
  const viewportRef = useRef<HTMLDivElement>(null);
  const [autoScrollEnabled, setAutoScrollEnabled] = useState(true);
  const [showScrollButton, setShowScrollButton] = useState(false);

  // Check if viewport is at bottom
  const isViewportAtBottom = useCallback(() => {
    const viewport = viewportRef.current;
    if (!viewport) return true;
    const { scrollTop, scrollHeight, clientHeight } = viewport;
    return scrollHeight - scrollTop - clientHeight < 50; // 50px threshold
  }, []);

  const handleWheel = useCallback(() => {
    // Only disable auto-scroll if user scrolls UP (away from bottom)
    // Check after a brief delay to let the scroll happen first
    if (autoScrollEnabled) {
      requestAnimationFrame(() => {
        if (!isViewportAtBottom()) {
          setAutoScrollEnabled(false);
          setShowScrollButton(true);
        }
      });
    }
  }, [autoScrollEnabled, isViewportAtBottom]);

  // Scroll detection logic
  const handleScroll = useCallback((event: React.UIEvent<HTMLDivElement>) => {
    const target = event.currentTarget;
    const { scrollTop, scrollHeight, clientHeight } = target;
    const isAtBottom = scrollHeight - scrollTop - clientHeight < 50; // 50px threshold

    if (isAtBottom) {
      // User reached bottom - hide button and re-enable auto-scroll
      setShowScrollButton(false);
      setAutoScrollEnabled(true);
    } else if (!autoScrollEnabled) {
      // User is not at bottom and auto-scroll is disabled - show button
      setShowScrollButton(true);
    }
  }, [autoScrollEnabled]);

  // Resume auto-scroll button handler
  const scrollToBottom = useCallback(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: 'smooth' });
      setAutoScrollEnabled(true);
      setShowScrollButton(false);
    }
  }, []);

  // Auto-scroll logic
  useEffect(() => {
    if (autoScrollEnabled && scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [currentMessages, streamingMessage?.content, streamingMessage?.thinkingContent, streamingMessage?.segments, autoScrollEnabled]);

  const hasMessages = currentMessages.length > 0 || streamingMessage;

  if (!hasMessages) {
    return null;
  }

  return (
    <div className={cn('relative flex-1 min-h-0', className)}>
      <ScrollArea
        className="h-full"
        viewportRef={viewportRef}
        viewportProps={{
          onScroll: handleScroll,
          onWheel: handleWheel,
        }}
      >
        <div ref={containerRef} className="p-4 md:p-6 max-w-3xl mx-auto">
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
                segments={streamingMessage.segments}
                thinkingContent={streamingMessage.thinkingContent}
              />
            )}

            {/* Scroll anchor */}
            <div ref={scrollRef} className="h-1" />
          </div>
        </div>
      </ScrollArea>

      {/* Scroll to bottom button */}
      {showScrollButton && (
        <Button
          variant="secondary"
          size="icon"
          className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full shadow-lg opacity-90 hover:opacity-100 z-10"
          onClick={scrollToBottom}
        >
          <ArrowDown className="h-4 w-4" />
        </Button>
      )}
    </div>
  );
}
