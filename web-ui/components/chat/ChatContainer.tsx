'use client';

import { useCallback, useEffect, useState } from 'react';
import { Plus, Sun, Moon } from 'lucide-react';
import { useAuth, UserButton } from '@clerk/nextjs';
import { GithubIcon } from '@/components/ui/icons';
import { Button } from '@/components/ui/button';
import { MessageList } from './MessageList';
import { InputArea } from './InputArea';
import { useStream } from '@/hooks/useWebSocket';
import { useChatStore } from '@/hooks/useChat';
import { StreamRequestError } from '@/lib/stream';
import type { StreamEvent, ToolCall, ResearchBrief, StreamingSnapshot } from '@/lib/types';
import { generateId } from '@/lib/utils';

function shouldAttemptResumeAfterSendFailure(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }

  if (error.name === 'AbortError') {
    return false;
  }

  if (error instanceof StreamRequestError && error.status !== undefined) {
    if (error.status === 409) {
      return false;
    }

    return error.status === 408 || error.status === 429 || error.status >= 500;
  }

  return true;
}

export function ChatContainer() {
  const { getToken } = useAuth();
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
    setProgressNode,
    hydrateStreaming,
    finishStreaming,
    setError,
    loadModels,
    newChat,
    isDeepResearch,
    toggleDeepResearch,
    canToggleDeepResearch,
    lockDeepResearch,
    droppedFeedCard,
    setDroppedFeedCard,
    clearDroppedFeedCard,
  } = useChatStore();

  const hasMessages = currentMessages.length > 0 || streamingMessage;

  const [isMobileViewport, setIsMobileViewport] = useState(false);
  const [mobileInputCollapsed, setMobileInputCollapsed] = useState(false);

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') {
      return;
    }
    const mq = window.matchMedia('(max-width: 639px)');
    const update = () => {
      setIsMobileViewport(mq.matches);
      if (!mq.matches) {
        setMobileInputCollapsed(false);
      }
    };
    update();
    mq.addEventListener('change', update);
    return () => mq.removeEventListener('change', update);
  }, []);

  useEffect(() => {
    if (!hasMessages) {
      setMobileInputCollapsed(false);
    }
  }, [hasMessages]);

  const handleViewportAtBottomChange = useCallback((atBottom: boolean) => {
    if (!isMobileViewport) return;
    if (!atBottom) {
      setMobileInputCollapsed(true);
    }
  }, [isMobileViewport]);

  const expandMobileInput = useCallback(() => {
    setMobileInputCollapsed(false);
  }, []);

  // Handle stream messages
  const handleStreamMessage = useCallback(
    (event: StreamEvent) => {
      switch (event.type) {
        case 'token':
          appendToken(event.data.content as string);
          break;
        case 'snapshot':
          hydrateStreaming(event.data as unknown as StreamingSnapshot);
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
        case 'progress':
          // Deep Research: node progress heartbeat
          setProgressNode(event.data.node as string);
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
      hydrateStreaming,
      appendThinking,
      addToolCallStart,
      updateToolCallEnd,
      setClarification,
      setBrief,
      setProgressNode,
      finishStreaming,
      setError,
    ]
  );

  const { sendMessage, resumeStream, stopStream, isStreaming, status } = useStream({
    onMessage: handleStreamMessage,
  });

  // Load models on mount
  useEffect(() => {
    const load = async () => {
      const token = await getToken();
      loadModels(token);
    };
    load();
  }, [loadModels, getToken]);

  // Handle send message
  const handleSend = useCallback(
    async (message: string) => {
      if (!sessionId) {
        setError('No session ID');
        return;
      }

      // Get fresh session token
      const token = await getToken();

      // Append dropped feed card URL as context for the backend
      const finalMessage = droppedFeedCard?.latest_url
        ? `${message}\n\n请参考这篇文章：${droppedFeedCard.latest_url}`
        : message;

      // Show original message + card attachment in UI (not the appended URL)
      addUserMessage(message, droppedFeedCard ?? undefined);
      clearDroppedFeedCard();

      const requestId = generateId();

      // Start streaming state
      startStreaming(requestId);

      // Send message via SSE stream
      try {
        await sendMessage(
          sessionId,
          finalMessage,
          requestId,
          currentModelProvider,
          currentModelName,
          isDeepResearch,
          token,
        );
      } catch (error) {
        if (!shouldAttemptResumeAfterSendFailure(error)) {
          const message = error instanceof Error ? error.message : 'Stream request failed';
          setError(message);
          return;
        }

        try {
          // Brief delay before resume to allow transient network issues to settle
          await new Promise(resolve => setTimeout(resolve, 500));
          await resumeStream(sessionId, token);
        } catch (resumeError) {
          const message = resumeError instanceof Error ? resumeError.message : 'Stream resume failed';
          setError(message);
        }
      }
    },
    [
      sessionId,
      currentModelProvider,
      currentModelName,
      isDeepResearch,
      droppedFeedCard,
      addUserMessage,
      startStreaming,
      sendMessage,
      resumeStream,
      setError,
      clearDroppedFeedCard,
      getToken,
    ]
  );

  // Handle stop streaming
  const handleStop = useCallback(() => {
    stopStream();
    finishStreaming();
  }, [stopStream, finishStreaming]);

  const handleNewChat = useCallback(async () => {
    const token = await getToken();
    newChat(token);
  }, [newChat, getToken]);

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
      <header className="sticky top-0 z-10 flex items-center justify-between gap-2 px-3 sm:px-4 py-2 sm:py-3 bg-background/80 backdrop-blur-sm">
        <div className="flex items-center gap-2 sm:gap-3 min-w-0">
          <h1 className="font-semibold text-base sm:text-lg whitespace-nowrap truncate">
            Research Agent
          </h1>
          {/* Streaming status indicator */}
          <div
            className={`shrink-0 w-2 h-2 rounded-full ${
              isStreaming
                ? 'bg-yellow-500 animate-pulse'
                : status === 'error'
                ? 'bg-red-500'
                : 'bg-green-500'
            }`}
            title={`Status: ${status}`}
          />
          <div className="hidden sm:block w-px h-4 bg-border mx-2" />
          <Button
            onClick={handleNewChat}
            disabled={isLoading || isStreaming}
            variant="outline"
            size="sm"
            className="shrink-0 gap-2 h-8 px-2 sm:h-9 sm:px-3"
            aria-label="New Chat"
          >
            <Plus className="h-4 w-4" />
            <span className="hidden sm:inline">New Chat</span>
          </Button>
        </div>

        <div className="flex items-center gap-1 sm:gap-2 shrink-0">
          <span className="text-xs text-muted-foreground hidden md:inline">
            {currentModelName}
          </span>
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleTheme}
            aria-label="Toggle theme"
            className="h-8 w-8 sm:h-9 sm:w-9"
          >
            <Sun className="h-4 w-4 dark:hidden" />
            <Moon className="h-4 w-4 hidden dark:block" />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            asChild
            className="h-8 w-8 sm:h-9 sm:w-9"
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
          <UserButton afterSignOutUrl="/" />
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-h-0">
        {!hasMessages ? (
          // Empty State: Centered Layout
          <div className="flex-1 flex flex-col justify-center pb-[4vh] sm:pb-[10vh]">
            <div className="w-full max-w-3xl mx-auto px-3 sm:px-4 mb-4 sm:mb-8">
              <div className="flex flex-col items-center justify-center text-center">
                <div className="mb-3 sm:mb-4 flex items-center justify-center">
                  <Sun className="w-7 h-7 sm:w-8 sm:h-8 text-primary animate-[spin_12s_linear_infinite]" />
                </div>
                <h2 className="text-xl sm:text-2xl font-semibold mb-2">Start Your Research</h2>
                <p className="text-sm sm:text-base text-muted-foreground max-w-md px-2">
                  Ask me about AI research, recent papers, tech trends, or anything else you&apos;d like to explore.
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
              droppedFeedCard={droppedFeedCard}
              onDropFeedCard={setDroppedFeedCard}
              onClearDroppedCard={clearDroppedFeedCard}
            />
          </div>
        ) : (
          // Active State: Standard Chat Layout
          <>
            <MessageList
              className="flex-1"
              onViewportAtBottomChange={handleViewportAtBottomChange}
            />
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
              droppedFeedCard={droppedFeedCard}
              onDropFeedCard={setDroppedFeedCard}
              onClearDroppedCard={clearDroppedFeedCard}
              mobileDockCollapsed={isMobileViewport && mobileInputCollapsed}
              onMobileDockExpand={expandMobileInput}
            />
          </>
        )}
      </main>
    </div>
  );
}
