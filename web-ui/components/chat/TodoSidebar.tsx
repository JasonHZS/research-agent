'use client';

import { memo, useState } from 'react';
import { Check, Circle, Loader2, ListTodo, ChevronUp, ChevronDown, PanelBottomClose } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useChatStore } from '@/hooks/useChat';
import type { TodoItem } from '@/lib/types';

/** Extract display text from a todo item — field name varies by framework */
function getTodoText(item: TodoItem): string {
  return item.todo || item.task || item.title || item.description || item.content || JSON.stringify(item);
}

function TodoStatusIcon({ status }: { status: TodoItem['status'] }) {
  switch (status) {
    case 'completed':
      return (
        <div className="flex items-center justify-center w-5 h-5 rounded-full bg-primary/15">
          <Check className="h-3 w-3 text-primary" />
        </div>
      );
    case 'in_progress':
      return (
        <div className="flex items-center justify-center w-5 h-5">
          <Loader2 className="h-3.5 w-3.5 text-primary spinner" />
        </div>
      );
    default:
      return (
        <div className="flex items-center justify-center w-5 h-5">
          <Circle className="h-3 w-3 text-muted-foreground/50" />
        </div>
      );
  }
}

function TodoItemRow({ item }: { item: TodoItem }) {
  const isCompleted = item.status === 'completed';
  const isActive = item.status === 'in_progress';

  return (
    <div
      className={cn(
        'flex items-start gap-2.5 px-3 py-2 transition-colors',
        isActive && 'bg-primary/5',
      )}
    >
      <div className="mt-0.5 shrink-0">
        <TodoStatusIcon status={item.status} />
      </div>
      <span
        className={cn(
          'text-sm leading-relaxed',
          isCompleted && 'text-muted-foreground line-through',
          isActive && 'text-foreground font-medium',
          !isCompleted && !isActive && 'text-muted-foreground',
        )}
      >
        {getTodoText(item)}
      </span>
    </div>
  );
}

/** Height of the collapsed mobile todo bar (header only) for padding calculations */
export const MOBILE_TODO_BAR_HEIGHT = 44;

export const TodoSidebar = memo(function TodoSidebar() {
  const todoItems = useChatStore((s) => s.todoItems);
  const isTodoSidebarVisible = useChatStore((s) => s.isTodoSidebarVisible);
  const hideTodoSidebar = useChatStore((s) => s.hideTodoSidebar);
  const showTodoSidebar = useChatStore((s) => s.showTodoSidebar);
  const [mobileExpanded, setMobileExpanded] = useState(false);

  if (todoItems.length === 0) return null;

  const completedCount = todoItems.filter((t) => t.status === 'completed').length;
  const totalCount = todoItems.length;
  const progress = totalCount > 0 ? (completedCount / totalCount) * 100 : 0;
  const handleHide = () => {
    setMobileExpanded(false);
    hideTodoSidebar();
  };

  if (!isTodoSidebarVisible) {
    return (
      <>
        <div className="hidden md:block fixed right-4 top-[4.25rem] z-20 animate-in slide-in-from-right-4 duration-300">
          <button
            type="button"
            onClick={showTodoSidebar}
            className="inline-flex items-center gap-2 rounded-full border border-border bg-background/95 px-3 py-2 text-xs font-medium text-foreground shadow-lg backdrop-blur-md transition-colors hover:bg-muted/70"
            title="展开 TODO"
            aria-label="展开 TODO"
          >
            <ListTodo className="h-4 w-4 text-primary" />
            <span>TODO {completedCount}/{totalCount}</span>
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          </button>
        </div>

        <div className="md:hidden fixed right-4 z-20 animate-in slide-in-from-bottom-4 duration-300 safe-bottom-4">
          <button
            type="button"
            onClick={showTodoSidebar}
            className="inline-flex items-center gap-2 rounded-full border border-border bg-background/95 px-3 py-2 text-xs font-medium text-foreground shadow-lg backdrop-blur-md transition-colors hover:bg-muted/70"
            title="显示 TODO"
            aria-label="显示 TODO"
          >
            <ListTodo className="h-4 w-4 text-primary" />
            <span>TODO {completedCount}/{totalCount}</span>
          </button>
        </div>
      </>
    );
  }

  return (
    <>
      {/* Desktop: floating panel below the top-right header actions */}
      <div className="hidden md:block fixed right-4 top-[4.25rem] z-20 w-[22rem] max-w-[calc(100vw-2rem)] animate-in slide-in-from-right-4 duration-300">
        <div className="overflow-hidden rounded-2xl border border-border bg-background/95 backdrop-blur-md shadow-xl">
          <div className="flex items-center justify-between px-3 py-2.5 border-b border-border bg-muted/30">
            <div className="flex items-center gap-2">
              <ListTodo className="h-4 w-4 text-primary" />
              <span className="text-xs font-medium text-foreground">
                TODO {completedCount}/{totalCount}
              </span>
            </div>
            <button
              type="button"
              onClick={handleHide}
              className="text-muted-foreground hover:text-foreground transition-colors p-0.5 rounded"
              title="折叠 TODO"
              aria-label="折叠 TODO"
            >
              <ChevronUp className="h-4 w-4" />
            </button>
          </div>
          <div className="h-0.5 bg-muted">
            <div
              className="h-full bg-primary transition-all duration-500 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="max-h-[60vh] overflow-y-auto divide-y divide-border/30">
            {todoItems.map((item, index) => (
              <TodoItemRow key={index} item={item} />
            ))}
          </div>
        </div>
      </div>

      {/* Mobile: fixed bottom bar, collapsible */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 z-20 animate-in slide-in-from-bottom-4 duration-300">
        <div className="border-t border-border bg-background/95 backdrop-blur-md shadow-[0_-4px_12px_rgba(0,0,0,0.1)] safe-pb-mobile-inset">
          {/* Header — sibling elements, no nested buttons */}
          <div className="flex items-center justify-between px-4 py-2.5">
            <div
              role="button"
              tabIndex={0}
              onClick={() => setMobileExpanded(!mobileExpanded)}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setMobileExpanded(!mobileExpanded); } }}
              className="flex items-center gap-2 flex-1 min-w-0 cursor-pointer"
            >
              <ListTodo className="h-4 w-4 text-primary shrink-0" />
              <span className="text-xs font-medium text-foreground">
                TODO {completedCount}/{totalCount}
              </span>
              {/* Inline mini progress bar */}
              <div className="w-16 h-1 bg-muted rounded-full overflow-hidden shrink-0">
                <div
                  className="h-full bg-primary transition-all duration-500 ease-out rounded-full"
                  style={{ width: `${progress}%` }}
                />
              </div>
              {mobileExpanded ? (
                <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
              ) : (
                <ChevronUp className="h-4 w-4 text-muted-foreground shrink-0" />
              )}
            </div>
            <button
              type="button"
              onClick={handleHide}
              className="text-muted-foreground hover:text-foreground transition-colors p-1 rounded shrink-0 ml-2"
              title="隐藏 TODO"
              aria-label="隐藏 TODO"
            >
              <PanelBottomClose className="h-3.5 w-3.5" />
            </button>
          </div>

          {/* Expanded todo list */}
          {mobileExpanded && (
            <div className="border-t border-border/50 max-h-[50vh] overflow-y-auto divide-y divide-border/30">
              {todoItems.map((item, index) => (
                <TodoItemRow key={index} item={item} />
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
});
