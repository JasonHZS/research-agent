'use client';

import { memo, useState, useCallback } from 'react';
import { User, Bot, Check, Copy, FileText } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { MarkdownRenderer } from './MarkdownRenderer';
import { ToolCallPanel } from './ToolCallPanel';
import type { ChatMessage, ToolCall, MessageSegment, FeedDigestItem } from '@/lib/types';

/** Map Deep Research graph node names to user-friendly labels */
const PROGRESS_NODE_LABELS: Record<string, string> = {
  working: '正在处理中...',
  clarify: '正在理解问题...',
  analyze: '正在分析需求...',
  plan_sections: '正在规划研究大纲...',
  discover: '正在搜索资料...',
  discover_tools: '正在搜索资料...',
  researcher: '正在深入研究...',
  researcher_tools: '正在深入研究...',
  extract_output: '正在提取内容...',
  compress_output: '正在整理内容...',
  aggregate: '正在汇总结果...',
  review: '正在审阅报告...',
  final_report: '正在撰写报告...',
};

interface MessageBubbleProps {
  message: ChatMessage;
  isStreaming?: boolean;
}

/**
 * Extract the final answer text from segments (only the last text segment)
 * This excludes intermediate text like "Let me try..." or error messages
 */
function getFinalAnswerContent(segments?: MessageSegment[], fallbackContent?: string): string {
  if (segments && segments.length > 0) {
    // Find the last text segment - this is typically the final answer
    const textSegments = segments.filter(
      (seg): seg is { type: 'text'; content: string } => seg.type === 'text'
    );
    if (textSegments.length > 0) {
      return textSegments[textSegments.length - 1].content;
    }
    return '';
  }
  return fallbackContent || '';
}

interface MessageActionsProps {
  /** Segments for extracting text-only content */
  segments?: MessageSegment[];
  /** Fallback content if no segments available */
  fallbackContent?: string;
}

/**
 * User message bubble with copy button on hover
 */
interface UserMessageBubbleProps {
  content: string;
  attachedFeedCard?: FeedDigestItem;
}

const UserMessageBubble = memo(function UserMessageBubble({ content, attachedFeedCard }: UserMessageBubbleProps) {
  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    if (!content) return;
    await navigator.clipboard.writeText(content);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  }, [content]);

  return (
    <div className="group relative flex flex-col items-end gap-2">
      {/* Attached feed card — shown above the message bubble */}
      {attachedFeedCard && (
        <a
          href={attachedFeedCard.latest_url ?? '#'}
          target="_blank"
          rel="noopener noreferrer"
          className="w-[200px] rounded-xl border border-orange-500/25 bg-orange-500/10 p-2.5 shadow-sm transition-colors hover:border-orange-500/50 hover:bg-orange-500/15"
        >
          <div className="mb-1.5 flex items-center gap-1.5">
            <FileText className="h-3 w-3 flex-shrink-0 text-orange-500/70" />
            <span className="truncate text-[10px] text-orange-600/70 dark:text-orange-400/70">
              {attachedFeedCard.feed_name}
            </span>
          </div>
          <p className="line-clamp-2 text-[11px] font-medium leading-snug text-foreground/80">
            {attachedFeedCard.latest_title_zh ?? attachedFeedCard.latest_title}
          </p>
        </a>
      )}
      <div className="rounded-2xl px-4 py-2.5 bg-primary text-primary-foreground rounded-br-md break-words">
        <p className="whitespace-pre-wrap">{content}</p>
      </div>
      {/* Copy button - appears on hover */}
      <Button
        variant="ghost"
        size="icon"
        className={cn(
          'absolute -left-8 top-1/2 -translate-y-1/2 h-6 w-6 rounded-md',
          'text-muted-foreground hover:bg-muted',
          'opacity-0 group-hover:opacity-100 transition-opacity'
        )}
        onClick={handleCopy}
        title="复制消息"
      >
        {isCopied ? (
          <Check className="h-3.5 w-3.5 text-green-500" />
        ) : (
          <Copy className="h-3.5 w-3.5" />
        )}
      </Button>
    </div>
  );
});

const MessageActions = memo(function MessageActions({ 
  segments, 
  fallbackContent 
}: MessageActionsProps) {
  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    const textContent = getFinalAnswerContent(segments, fallbackContent);
    if (!textContent) return;
    await navigator.clipboard.writeText(textContent);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  }, [segments, fallbackContent]);

  // Don't show copy button if there's no text content
  const hasTextContent = getFinalAnswerContent(segments, fallbackContent).length > 0;
  if (!hasTextContent) return null;

  return (
    <div className="flex items-center gap-2 mt-1">
      <Button
        variant="ghost"
        size="icon"
        className="h-6 w-6 rounded-md hover:bg-muted text-muted-foreground"
        onClick={handleCopy}
        title="Copy text content"
      >
        {isCopied ? (
          <Check className="h-3.5 w-3.5 text-green-500" />
        ) : (
          <Copy className="h-3.5 w-3.5" />
        )}
      </Button>
    </div>
  );
});

/**
 * Renders a single message segment (text or tool calls)
 */
interface SegmentRendererProps {
  segment: MessageSegment;
  /** Whether to show cursor at the end of this segment */
  showCursor?: boolean;
}

const SegmentRenderer = memo(function SegmentRenderer({
  segment,
  showCursor = false,
}: SegmentRendererProps) {
  if (segment.type === 'tool_calls') {
    return <ToolCallPanel toolCalls={segment.toolCalls} className="w-full" />;
  }
  
  // Text segment
  return (
    <div className="w-full break-words">
      <div className="prose-container">
        <MarkdownRenderer content={segment.content} />
        {/* Blinking cursor - inline at end of text */}
        {showCursor && (
          <span className="inline-block w-2 h-4 bg-primary ml-0.5 cursor-blink" />
        )}
      </div>
    </div>
  );
});

/**
 * Standalone blinking cursor component for when cursor needs to be on its own line
 */
const StreamingCursor = memo(function StreamingCursor() {
  return (
    <div className="w-full">
      <span className="inline-block w-2 h-4 bg-primary cursor-blink" />
    </div>
  );
});

export const MessageBubble = memo(function MessageBubble({
  message,
  isStreaming = false,
}: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isAssistant = message.role === 'assistant';
  
  // Check if we have segments for interleaved display
  const hasSegments = isAssistant && message.segments && message.segments.length > 0;

  return (
    <div
      className={cn(
        'flex gap-3 message-enter',
        isUser ? 'flex-row-reverse' : 'flex-row'
      )}
    >
      {/* Message content */}
      <div
        className={cn(
          'flex flex-col gap-2 min-w-0',
          isUser ? 'items-end max-w-[80%]' : 'items-start w-full'
        )}
      >
        {/* Interleaved segments rendering */}
        {hasSegments && message.segments!.map((segment, index) => (
          <SegmentRenderer
            key={index}
            segment={segment}
            showCursor={false}
          />
        ))}
        
        {/* Fallback: Legacy rendering for messages without segments */}
        {isAssistant && !hasSegments && (
          <>
            {/* Tool calls panel - rendered before content */}
            {message.tool_calls && message.tool_calls.length > 0 && (
              <ToolCallPanel toolCalls={message.tool_calls} className="w-full" />
            )}
            {/* Message content */}
            <div className="w-full break-words">
              <div className="prose-container">
                <MarkdownRenderer content={message.content} />
                {isStreaming && (
                  <span className="inline-block w-2 h-4 bg-primary ml-0.5 cursor-blink" />
                )}
              </div>
            </div>
          </>
        )}

        {/* User message bubble */}
        {isUser && (
          <UserMessageBubble content={message.content} attachedFeedCard={message.attachedFeedCard} />
        )}

        {/* Message Actions (Copy) */}
        {isAssistant && !isStreaming && (
          <MessageActions 
            segments={message.segments} 
            fallbackContent={message.content} 
          />
        )}
      </div>
    </div>
  );
});

// Streaming message bubble variant
interface StreamingMessageBubbleProps {
  content: string;
  toolCalls: ToolCall[];
  /** Segments for interleaved display */
  segments?: MessageSegment[];
  thinkingContent?: string;
  /** Current progress node (Deep Research mode) */
  progressNode?: string | null;
}

export const StreamingMessageBubble = memo(function StreamingMessageBubble({
  content,
  toolCalls,
  segments = [],
  thinkingContent,
  progressNode,
}: StreamingMessageBubbleProps) {
  // Use segments if available, otherwise fall back to legacy rendering
  const hasSegments = segments.length > 0;
  
  return (
    <div className="flex gap-3 flex-row message-enter">
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

        {/* Deep Research progress indicator — shown alongside content */}
        {progressNode && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground animate-pulse">
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-primary" />
            <span>{PROGRESS_NODE_LABELS[progressNode] ?? progressNode}</span>
          </div>
        )}

        {/* Interleaved segments rendering */}
        {hasSegments && (() => {
          const lastSegment = segments[segments.length - 1];
          const lastIsText = lastSegment?.type === 'text';
          
          return (
            <>
              {segments.map((segment, index) => {
                const isLast = index === segments.length - 1;
                // Show cursor inline only if this is the last segment AND it's a text segment
                const showCursor = isLast && lastIsText;
                
                return (
                  <SegmentRenderer
                    key={index}
                    segment={segment}
                    showCursor={showCursor}
                  />
                );
              })}
              {/* Standalone cursor after tool_calls (when last segment is not text) */}
              {!lastIsText && <StreamingCursor />}
            </>
          );
        })()}
        
        {/* Fallback: Legacy rendering for when segments are not used */}
        {!hasSegments && (
          <>
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
                  <span className="inline-block w-2 h-4 bg-primary ml-0.5 cursor-blink" />
                </div>
              </div>
            )}
          </>
        )}
        
        {/* Actions for streaming bubble */}
        {content && (
          <MessageActions 
            segments={segments} 
            fallbackContent={content} 
          />
        )}
      </div>
    </div>
  );
});
