'use client';

import { useState, memo } from 'react';
import {
  Loader2,
  Check,
  XCircle,
  Wrench,
  Search,
  FileText,
  Globe,
  Database,
  ChevronDown,
  ChevronRight,
  Terminal,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ToolCall } from '@/lib/api';

// Tool icon mapping
const TOOL_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  search: Search,
  read: FileText,
  fetch: Globe,
  query: Database,
  execute: Terminal,
  default: Wrench,
};

function getToolIcon(name: string): React.ComponentType<{ className?: string }> {
  const lowerName = name.toLowerCase();
  for (const [key, icon] of Object.entries(TOOL_ICONS)) {
    if (lowerName.includes(key)) {
      return icon;
    }
  }
  return TOOL_ICONS.default;
}

interface ToolCallItemProps {
  toolCall: ToolCall;
}

function ToolCallItem({ toolCall }: ToolCallItemProps) {
  const [isOpen, setIsOpen] = useState(false);
  const Icon = getToolIcon(toolCall.name);
  const isRunning = toolCall.status === 'running';
  const isCompleted = toolCall.status === 'completed';
  const isFailed = toolCall.status === 'failed';

  // Format arguments for display
  const argsString = toolCall.args
    ? Object.entries(toolCall.args)
        .map(([key, value]) => `${key}=${JSON.stringify(value)}`)
        .join(', ')
    : '';

  return (
    <div className="flex flex-col border-b border-border/50 last:border-0 text-sm">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 w-full py-2 px-3 hover:bg-muted/50 transition-colors text-left"
      >
        <div className="shrink-0 text-muted-foreground">
          {isOpen ? (
            <ChevronDown className="h-3.5 w-3.5" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5" />
          )}
        </div>

        <Icon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />

        <div className="flex-1 min-w-0 flex items-center gap-2">
          <span className="font-medium truncate">{toolCall.name}</span>
          {!isOpen && argsString && (
            <span className="text-muted-foreground truncate opacity-70 text-xs font-mono">
              ({argsString})
            </span>
          )}
        </div>

        {isRunning && (
          <Loader2 className="h-3.5 w-3.5 text-primary spinner shrink-0 ml-2" />
        )}
        {isCompleted && (
          <Check className="h-3.5 w-3.5 text-green-500 shrink-0 ml-2" />
        )}
        {isFailed && (
          <XCircle className="h-3.5 w-3.5 text-destructive shrink-0 ml-2" />
        )}
      </button>

      {/* Expanded Details */}
      {isOpen && (
        <div className="px-9 pb-3 pt-0 text-xs font-mono overflow-x-auto">
          {/* Arguments */}
          {argsString && (
            <div className="mb-2">
              <span className="text-muted-foreground select-none">$ </span>
              <span className="text-primary">{toolCall.name}</span>{' '}
              <span className="text-foreground">{argsString}</span>
            </div>
          )}

          {/* Result (if completed) */}
          {isCompleted && toolCall.result && (
            <div className="mt-2 text-muted-foreground bg-muted/30 p-2 rounded border border-border/50 whitespace-pre-wrap max-h-60 overflow-y-auto">
              {toolCall.result}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

interface ToolCallPanelProps {
  toolCalls: ToolCall[];
  className?: string;
}

export const ToolCallPanel = memo(function ToolCallPanel({
  toolCalls,
  className,
}: ToolCallPanelProps) {
  if (toolCalls.length === 0) return null;

  return (
    <div
      className={cn(
        'border border-border rounded-lg bg-card/50 overflow-hidden',
        className
      )}
    >
      <div className="px-3 py-2 bg-muted/30 border-b border-border">
        <span className="text-xs font-medium text-muted-foreground">
          Tool Calls ({toolCalls.length})
        </span>
      </div>
      <div className="divide-y divide-border">
        {toolCalls.map((toolCall) => (
          <ToolCallItem key={toolCall.id} toolCall={toolCall} />
        ))}
      </div>
    </div>
  );
});
