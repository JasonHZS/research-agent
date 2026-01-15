'use client';

import { memo } from 'react';
import { User, Bot } from 'lucide-react';
import { cn } from '@/lib/utils';
import { MarkdownRenderer } from './MarkdownRenderer';
import { ToolCallPanel } from './ToolCallPanel';
import type { ChatMessage, ToolCall } from '@/lib/api';

interface MessageBubbleProps {
  message: ChatMessage;
  isStreaming?: boolean;
}

export const MessageBubble = memo(function MessageBubble({
  message,
  isStreaming = false,
}: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isAssistant = message.role === 'assistant';

  return (
    <div
      className={cn(
        'flex gap-3 message-enter',
        isUser ? 'flex-row-reverse' : 'flex-row'
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          'shrink-0 w-8 h-8 rounded-full flex items-center justify-center',
          isUser ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Message content */}
      <div
        className={cn(
          'flex flex-col gap-2 min-w-0',
          isUser ? 'items-end max-w-[80%]' : 'items-start w-full'
        )}
      >
        {/* Tool calls panel for assistant messages - Rendered BEFORE content */}
        {isAssistant && message.tool_calls && message.tool_calls.length > 0 && (
          <ToolCallPanel toolCalls={message.tool_calls} className="w-full" />
        )}

        {/* Message bubble */}
        <div
          className={cn(
            'break-words',
            isUser
              ? 'rounded-2xl px-4 py-2.5 bg-primary text-primary-foreground rounded-br-md'
              : 'w-full'
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="prose-container">
              <MarkdownRenderer content={message.content} />
              {/* Blinking cursor for streaming */}
              {isStreaming && (
                <span className="inline-block w-2 h-4 bg-foreground/70 ml-0.5 cursor-blink" />
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
});

// Streaming message bubble variant
interface StreamingMessageBubbleProps {
  content: string;
  toolCalls: ToolCall[];
  thinkingContent?: string;
}

export const StreamingMessageBubble = memo(function StreamingMessageBubble({
  content,
  toolCalls,
  thinkingContent,
}: StreamingMessageBubbleProps) {
  return (
    <div className="flex gap-3 flex-row message-enter">
      {/* Avatar */}
      <div className="shrink-0 w-8 h-8 rounded-full flex items-center justify-center bg-muted text-muted-foreground">
        <Bot className="h-4 w-4" />
      </div>

      {/* Message content */}
      <div className="flex flex-col gap-2 w-full min-w-0 items-start">
        {/* Thinking content (collapsed by default) */}
        {thinkingContent && (
          <div className="bg-muted/50 border border-border rounded-lg px-3 py-2 text-sm text-muted-foreground w-full">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-medium">Thinking...</span>
            </div>
            <p className="whitespace-pre-wrap text-xs opacity-70 line-clamp-3">
              {thinkingContent}
            </p>
          </div>
        )}

        {/* Tool calls panel */}
        {toolCalls.length > 0 && (
          <ToolCallPanel toolCalls={toolCalls} className="w-full" />
        )}

        {/* Message bubble */}
        {(content || toolCalls.length === 0) && (
          <div className="w-full break-words">
            <div className="prose-container">
              {content ? (
                <MarkdownRenderer content={content} />
              ) : (
                <span className="text-muted-foreground">Generating response...</span>
              )}
              {/* Blinking cursor */}
              <span className="inline-block w-2 h-4 bg-foreground/70 ml-0.5 cursor-blink" />
            </div>
          </div>
        )}
      </div>
    </div>
  );
});
