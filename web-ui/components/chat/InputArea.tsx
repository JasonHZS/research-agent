'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { Send, StopCircle, Loader2, Sparkles, Newspaper, ScrollText, ArrowRight } from 'lucide-react';
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
  isDeepResearch?: boolean;
  onToggleDeepResearch?: () => void;
  showExamples?: boolean;
}

export function InputArea({
  onSend,
  onStop,
  isStreaming = false,
  disabled = false,
  placeholder = 'Research anything...',
  className,
  isDeepResearch = false,
  onToggleDeepResearch,
  showExamples = false,
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
        <div className="relative flex flex-col gap-2 bg-card border border-border rounded-2xl px-4 py-3 shadow-sm transition-shadow duration-300 focus-within:shadow-[0_0_20px_hsl(var(--primary)/0.4),0_0_40px_hsl(var(--primary)/0.2)] focus-within:border-primary/50">
          {/* Input textarea */}
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            rows={1}
            className="w-full resize-none bg-transparent border-0 outline-none text-foreground placeholder:text-muted-foreground min-h-[60px] max-h-[300px] py-1 scrollbar-thin"
          />

          <div className="flex items-center justify-between">
            {/* Deep Research Toggle */}
            <div className="flex items-center">
              {onToggleDeepResearch && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={onToggleDeepResearch}
                  className={cn(
                    "deep-research-btn h-7 gap-1.5 px-3 text-xs font-medium rounded-lg border transition-all duration-200",
                    isDeepResearch 
                      ? "active" 
                      : "text-muted-foreground hover:text-foreground hover:bg-muted border-transparent"
                  )}
                  title={isDeepResearch ? "Deep Research Mode On" : "Enable Deep Research Mode"}
                >
                  Deep Research
                </Button>
              )}
            </div>

            <div className="flex items-center gap-2">
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
          </div>
        </div>

        {/* Hint text */}
        <p className="text-xs text-muted-foreground text-center mt-2">
          Press <kbd className="px-1 py-0.5 bg-muted rounded text-[10px]">Enter</kbd> to send,{' '}
          <kbd className="px-1 py-0.5 bg-muted rounded text-[10px]">Shift + Enter</kbd> for new line
        </p>

        {/* Example Queries */}
        {showExamples && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-6 px-4 max-w-2xl mx-auto">
          <button
            onClick={() => setInput('今天 hacker news 上有什么关于 AI 的帖子， 帮我总结一下其主要内容和评论区')}
            className="group relative overflow-hidden rounded-2xl p-5 h-36 text-left transition-all duration-300 hover:shadow-lg hover:-translate-y-0.5 hover:scale-[1.01] border border-orange-200/50 dark:border-orange-800/30"
          >
            {/* Gradient Background */}
            <div className="absolute inset-0 bg-gradient-to-br from-orange-100/80 via-amber-50/50 to-orange-50/80 dark:from-orange-900/20 dark:via-amber-900/10 dark:to-orange-900/20 opacity-100 transition-opacity" />
            
            <div className="relative z-10 flex flex-col h-full justify-between">
              <div className="space-y-1">
                <h3 className="text-lg font-bold text-orange-950 dark:text-orange-50 font-serif tracking-tight">
                  Hacker News 热点
                </h3>
                <p className="text-xs font-medium text-orange-900/70 dark:text-orange-100/60 leading-relaxed">
                  探索今日关于 AI 的热门讨论与社区洞见。
                </p>
              </div>
              
              <div className="flex items-center gap-2 mt-auto">
                <div className="p-1.5 bg-orange-500/10 rounded-full backdrop-blur-sm group-hover:bg-orange-500/20 transition-colors">
                   <Newspaper className="w-3.5 h-3.5 text-orange-700 dark:text-orange-300" />
                </div>
                <span className="text-[10px] font-semibold text-orange-800 dark:text-orange-200 flex items-center gap-1">
                  探索趋势 <ArrowRight className="w-2.5 h-2.5 opacity-0 -ml-2 group-hover:opacity-100 group-hover:ml-0 transition-all duration-300" />
                </span>
              </div>
            </div>
          </button>

          <button
            onClick={() => setInput('最近一周huggingface 上的 top5 paper 都有哪些？帮我总结一下')}
            className="group relative overflow-hidden rounded-2xl p-5 h-36 text-left transition-all duration-300 hover:shadow-lg hover:-translate-y-0.5 hover:scale-[1.01] border border-orange-200/50 dark:border-orange-800/30"
          >
            {/* Gradient Background */}
            <div className="absolute inset-0 bg-gradient-to-br from-amber-100/80 via-orange-50/50 to-amber-50/80 dark:from-amber-900/20 dark:via-orange-900/10 dark:to-amber-900/20 opacity-100 transition-opacity" />
            
            <div className="relative z-10 flex flex-col h-full justify-between">
              <div className="space-y-1">
                <h3 className="text-lg font-bold text-amber-950 dark:text-amber-50 font-serif tracking-tight">
                  前沿论文精选
                </h3>
                <p className="text-xs font-medium text-amber-900/70 dark:text-amber-100/60 leading-relaxed">
                  总结本周 Hugging Face 上最热门的 5 篇论文。
                </p>
              </div>
              
              <div className="flex items-center gap-2 mt-auto">
                <div className="p-1.5 bg-amber-500/10 rounded-full backdrop-blur-sm group-hover:bg-amber-500/20 transition-colors">
                   <ScrollText className="w-3.5 h-3.5 text-amber-700 dark:text-amber-300" />
                </div>
                <span className="text-[10px] font-semibold text-amber-800 dark:text-amber-200 flex items-center gap-1">
                  阅读总结 <ArrowRight className="w-2.5 h-2.5 opacity-0 -ml-2 group-hover:opacity-100 group-hover:ml-0 transition-all duration-300" />
                </span>
              </div>
            </div>
          </button>
        </div>
        )}
      </div>
    </div>
  );
}
