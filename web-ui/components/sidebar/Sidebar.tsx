'use client';

import { useCallback } from 'react';
import { Plus, PanelLeftClose, PanelLeft, Sun, Moon, MessageSquare } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ModelSelector } from './ModelSelector';
import { useChatStore } from '@/hooks/useChat';
import { cn } from '@/lib/utils';

interface SidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  className?: string;
}

export function Sidebar({ isOpen, onToggle, className }: SidebarProps) {
  const { newChat, isLoading, currentMessages } = useChatStore();

  const handleNewChat = useCallback(() => {
    newChat();
  }, [newChat]);

  // Theme toggle (basic implementation)
  const toggleTheme = useCallback(() => {
    const html = document.documentElement;
    if (html.classList.contains('dark')) {
      html.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    } else {
      html.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    }
  }, []);

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-background/80 backdrop-blur-sm z-40 md:hidden"
          onClick={onToggle}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed md:relative inset-y-0 left-0 z-50 flex flex-col w-72 bg-card border-r border-border transition-transform duration-300 ease-in-out',
          isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0 md:w-0 md:min-w-0 md:overflow-hidden',
          className
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
              <span className="text-primary-foreground font-bold text-sm">R</span>
            </div>
            <span className="font-semibold">Research</span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onToggle}
            className="hidden md:flex"
          >
            {isOpen ? (
              <PanelLeftClose className="h-5 w-5" />
            ) : (
              <PanelLeft className="h-5 w-5" />
            )}
          </Button>
        </div>

        {/* New Chat Button */}
        <div className="p-3">
          <Button
            onClick={handleNewChat}
            disabled={isLoading}
            className="w-full justify-start gap-2"
            variant="outline"
          >
            <Plus className="h-4 w-4" />
            New Chat
          </Button>
        </div>

        {/* Session Info (replaces conversation list) */}
        <div className="flex-1 p-3">
          <div className="text-sm text-muted-foreground mb-2">Current Session</div>
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-accent">
            <MessageSquare className="h-4 w-4 shrink-0 text-muted-foreground" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">
                {currentMessages.length > 0
                  ? `${currentMessages.length} messages`
                  : 'New conversation'}
              </p>
              <p className="text-xs text-muted-foreground">
                Session active
              </p>
            </div>
          </div>
          <p className="text-xs text-muted-foreground mt-3 px-1">
            Messages are not persisted. Starting a new chat will clear the current conversation.
          </p>
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-border space-y-3">
          {/* Model Selector */}
          <ModelSelector />

          {/* Theme Toggle */}
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleTheme}
            className="w-full justify-start gap-2"
          >
            <Sun className="h-4 w-4 dark:hidden" />
            <Moon className="h-4 w-4 hidden dark:block" />
            <span className="dark:hidden">Light Mode</span>
            <span className="hidden dark:block">Dark Mode</span>
          </Button>
        </div>
      </aside>

      {/* Collapsed state toggle for desktop */}
      {!isOpen && (
        <Button
          variant="ghost"
          size="icon"
          onClick={onToggle}
          className="hidden md:flex fixed top-4 left-4 z-50"
        >
          <PanelLeft className="h-5 w-5" />
        </Button>
      )}
    </>
  );
}
