'use client';

import { memo, useCallback } from 'react';
import { MessageSquare, Trash2, MoreHorizontal } from 'lucide-react';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useChatStore } from '@/hooks/useChat';
import { cn, formatTime, truncate } from '@/lib/utils';
import type { ConversationSummary } from '@/lib/api';

interface ConversationItemProps {
  conversation: ConversationSummary;
  isActive: boolean;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

const ConversationItem = memo(function ConversationItem({
  conversation,
  isActive,
  onSelect,
  onDelete,
}: ConversationItemProps) {
  return (
    <div
      className={cn(
        'group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors',
        isActive
          ? 'bg-accent text-accent-foreground'
          : 'hover:bg-muted/50'
      )}
      onClick={() => onSelect(conversation.id)}
    >
      <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">
          {truncate(conversation.title, 30)}
        </p>
        <p className="text-xs text-muted-foreground">
          {formatTime(conversation.updated_at)}
        </p>
      </div>

      {/* Actions dropdown */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
            onClick={(e) => e.stopPropagation()}
          >
            <MoreHorizontal className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            className="text-destructive focus:text-destructive"
            onClick={(e) => {
              e.stopPropagation();
              onDelete(conversation.id);
            }}
          >
            <Trash2 className="h-4 w-4 mr-2" />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
});

interface ConversationListProps {
  className?: string;
}

export function ConversationList({ className }: ConversationListProps) {
  const {
    conversations,
    currentConversationId,
    loadConversation,
    deleteConversation,
    isLoading,
  } = useChatStore();

  const handleSelect = useCallback(
    (id: string) => {
      if (id !== currentConversationId) {
        loadConversation(id);
      }
    },
    [currentConversationId, loadConversation]
  );

  const handleDelete = useCallback(
    (id: string) => {
      if (confirm('Are you sure you want to delete this conversation?')) {
        deleteConversation(id);
      }
    },
    [deleteConversation]
  );

  if (isLoading && conversations.length === 0) {
    return (
      <div className={cn('flex items-center justify-center py-8', className)}>
        <div className="text-sm text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (conversations.length === 0) {
    return (
      <div className={cn('flex flex-col items-center justify-center py-8 px-4', className)}>
        <MessageSquare className="h-8 w-8 text-muted-foreground mb-2" />
        <p className="text-sm text-muted-foreground text-center">
          No conversations yet
        </p>
      </div>
    );
  }

  return (
    <ScrollArea className={cn('flex-1', className)}>
      <div className="space-y-1 p-2">
        {conversations.map((conversation) => (
          <ConversationItem
            key={conversation.id}
            conversation={conversation}
            isActive={conversation.id === currentConversationId}
            onSelect={handleSelect}
            onDelete={handleDelete}
          />
        ))}
      </div>
    </ScrollArea>
  );
}
