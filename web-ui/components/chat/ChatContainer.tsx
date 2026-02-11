'use client';

import { useCallback, useEffect } from 'react';
import { Plus, Sun, Moon } from 'lucide-react';
import { GithubIcon } from '@/components/ui/icons';
import { Button } from '@/components/ui/button';
import { MessageList } from './MessageList';
import { InputArea } from './InputArea';
import { useStream } from '@/hooks/useWebSocket';
import { useChatStore } from '@/hooks/useChat';
import type { StreamEvent, ToolCall, ResearchBrief } from '@/lib/types';
import { generateId } from '@/lib/utils';

export function ChatContainer() {
  const {
    sessionId,
    currentModelProvider,
    currentModelName,
    currentMessages,
    streamingMessage,
    isLoading,
    addUserMessage,
    startStreaming,
    appendToken,
    appendThinking,
    addToolCallStart,
    updateToolCallEnd,
    setClarification,
    setBrief,
    finishStreaming,
    setError,
    loadModels,
    newChat,
    isDeepResearch,
    toggleDeepResearch,
    canToggleDeepResearch,
    lockDeepResearch,
  } = useChatStore();

  const hasMessages = currentMessages.length > 0 || streamingMessage;

  // Handle stream messages
  const handleStreamMessage = useCallback(
    (event: StreamEvent) => {
      switch (event.type) {
        case 'token':
          appendToken(event.data.content as string);
          break;
        case 'thinking':
          appendThinking(event.data.content as string);
          break;
        case 'tool_call_start':
          addToolCallStart(event.data as unknown as ToolCall);
          break;
        case 'tool_call_end':
          updateToolCallEnd(event.data as unknown as ToolCall);
          break;
        case 'clarification':
          // Deep Research: set clarification question
          setClarification(event.data.question as string);
          break;
        case 'brief':
          // Deep Research: set research brief
          setBrief(event.data as unknown as ResearchBrief);
          break;
        case 'message_complete':
          // Pass isClarification flag from server
          finishStreaming({ 
            isClarification: event.data.is_clarification as boolean | undefined 
          });
          break;
        case 'error':
          setError(event.data.message as string);
          finishStreaming();
          break;
      }
    },
    [
      appendToken,
      appendThinking,
      addToolCallStart,
      updateToolCallEnd,
      setClarification,
      setBrief,
      finishStreaming,
      setError,
    ]
  );

  const { sendMessage, stopStream, isStreaming, status } = useStream({
    onMessage: handleStreamMessage,
  });

  // Load models on mount
  useEffect(() => {
    loadModels();
  }, [loadModels]);

  // Handle send message
  const handleSend = useCallback(
    async (message: string) => {
      if (!sessionId) {
        setError('No session ID');
        return;
      }

      // Add user message to UI
      addUserMessage(message);

      const requestId = generateId();

      // Start streaming state
      startStreaming(requestId);

      // Send message via SSE stream
      await sendMessage(sessionId, message, currentModelProvider, currentModelName, isDeepResearch);
    },
    [
      sessionId,
      currentModelProvider,
      currentModelName,
      isDeepResearch,
      addUserMessage,
      startStreaming,
      sendMessage,
      setError,
    ]
  );

  // Handle stop streaming
  const handleStop = useCallback(() => {
    stopStream();
    finishStreaming();
  }, [stopStream, finishStreaming]);

  const handleNewChat = useCallback(() => {
    newChat();
  }, [newChat]);

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
    <div className="flex flex-col h-full relative">
      {/* Header - Floating on top */}
      <header className="absolute top-0 left-0 right-0 z-10 flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-3">
          <h1 className="font-semibold text-lg">Research Agent</h1>
          {/* Streaming status indicator */}
          <div
            className={`w-2 h-2 rounded-full ${
              isStreaming
                ? 'bg-yellow-500 animate-pulse'
                : status === 'error'
                ? 'bg-red-500'
                : 'bg-green-500'
            }`}
            title={`Status: ${status}`}
          />
          <div className="w-px h-4 bg-border mx-2" />
          <Button
            onClick={handleNewChat}
            disabled={isLoading || isStreaming}
            variant="outline"
            size="sm"
            className="gap-2"
          >
            <Plus className="h-4 w-4" />
            New Chat
          </Button>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground hidden sm:inline">
            {currentModelName}
          </span>
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleTheme}
            aria-label="Toggle theme"
            className="h-9 w-9"
          >
            <Sun className="h-4 w-4 dark:hidden" />
            <Moon className="h-4 w-4 hidden dark:block" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            asChild
            className="h-9 w-9"
          >
            <a
              href="https://github.com/JasonHZS/research-agent"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="View on GitHub"
            >
              <GithubIcon className="h-5 w-5" />
            </a>
          </Button>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-h-0">
        {!hasMessages ? (
          // Empty State: Centered Layout
          <div className="flex-1 flex flex-col justify-center pb-[10vh]">
            <div className="w-full max-w-3xl mx-auto px-4 mb-8">
              <div className="flex flex-col items-center justify-center text-center">
                <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mb-4">
                  <Sun className="w-8 h-8 text-primary animate-[spin_12s_linear_infinite]" />
                </div>
                <h2 className="text-2xl font-semibold mb-2">Start Your Research</h2>
                <p className="text-muted-foreground max-w-md">
                  Ask me about AI research, recent papers, tech trends, or anything else you'd like to explore.
                </p>
              </div>
            </div>

            <InputArea
              onSend={handleSend}
              onStop={handleStop}
              isStreaming={!!streamingMessage}
              disabled={false}
              placeholder={isDeepResearch ? "Deep Research Mode enabled..." : "Explore cutting-edge AI research..."}
              isDeepResearch={isDeepResearch}
              onToggleDeepResearch={toggleDeepResearch}
              canToggleDeepResearch={canToggleDeepResearch}
              onLockDeepResearch={lockDeepResearch}
              showExamples={true}
            />
          </div>
        ) : (
          // Active State: Standard Chat Layout
          <>
            <MessageList className="flex-1" />
            <InputArea
              onSend={handleSend}
              onStop={handleStop}
              isStreaming={!!streamingMessage}
              disabled={false}
              placeholder={isDeepResearch ? "Deep Research Mode enabled..." : "Explore cutting-edge AI research..."}
              isDeepResearch={isDeepResearch}
              onToggleDeepResearch={toggleDeepResearch}
              canToggleDeepResearch={canToggleDeepResearch}
              onLockDeepResearch={lockDeepResearch}
              showExamples={false}
            />
          </>
        )}
      </main>
    </div>
  );
}
