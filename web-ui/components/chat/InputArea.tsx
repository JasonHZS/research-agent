'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { Send, StopCircle, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { ModelSelector } from '@/components/sidebar/ModelSelector';
import { cn } from '@/lib/utils';

interface InputAreaProps {
  onSend: (message: string) => void;
  onStop?: () => void;
  isStreaming?: boolean;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
}

export function InputArea({
  onSend,
  onStop,
  isStreaming = false,
  disabled = false,
  placeholder = 'Research anything...',
  className,
}: InputAreaProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  const adjustHeight = useCallback(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 300)}px`;
    }
  }, []);

  useEffect(() => {
    adjustHeight();
  }, [input, adjustHeight]);

  // Handle submit
  const handleSubmit = useCallback(() => {
    const trimmedInput = input.trim();
    if (!trimmedInput || disabled || isStreaming) return;

    onSend(trimmedInput);
    setInput('');

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [input, disabled, isStreaming, onSend]);

  // Handle keyboard shortcuts
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      // Submit on Enter (without Shift)
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit]
  );

  return (
    <div className={cn('bg-background p-4', className)}>
      <div className="max-w-3xl mx-auto">
        <div className="relative flex items-end gap-2 bg-card border border-border rounded-2xl px-4 py-2 shadow-sm transition-shadow duration-300 focus-within:shadow-[0_0_20px_hsl(var(--primary)/0.4),0_0_40px_hsl(var(--primary)/0.2)] focus-within:border-primary/50">
          {/* Input textarea */}
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            rows={1}
            className="flex-1 resize-none bg-transparent border-0 outline-none text-foreground placeholder:text-muted-foreground min-h-[94px] max-h-[300px] py-1 scrollbar-thin"
          />

          <ModelSelector
            buttonVariant="ghost"
            buttonSize="sm"
            fullWidth={false}
            align="end"
            className="h-8 rounded-full px-3 text-xs"
          />

          {/* Action button */}
          {isStreaming ? (
            <Button
              variant="ghost"
              size="icon"
              onClick={onStop}
              className="shrink-0 h-8 w-8 text-destructive hover:text-destructive hover:bg-destructive/10"
            >
              <StopCircle className="h-5 w-5" />
            </Button>
          ) : (
            <Button
              variant="ghost"
              size="icon"
              onClick={handleSubmit}
              disabled={!input.trim() || disabled}
              className="shrink-0 h-8 w-8 text-primary hover:text-primary hover:bg-primary/10 disabled:opacity-50"
            >
              {disabled ? (
                <Loader2 className="h-5 w-5 spinner" />
              ) : (
                <Send className="h-5 w-5" />
              )}
            </Button>
          )}
        </div>

        {/* Hint text */}
        <p className="text-xs text-muted-foreground text-center mt-2">
          Press <kbd className="px-1 py-0.5 bg-muted rounded text-[10px]">Enter</kbd> to send,{' '}
          <kbd className="px-1 py-0.5 bg-muted rounded text-[10px]">Shift + Enter</kbd> for new line
        </p>
      </div>
    </div>
  );
}
