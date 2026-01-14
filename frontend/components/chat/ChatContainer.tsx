'use client';

import { useCallback, useEffect } from 'react';
import { Menu, Settings } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { MessageList } from './MessageList';
import { InputArea } from './InputArea';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useChatStore } from '@/hooks/useChat';
import type { WebSocketEvent, ToolCall } from '@/lib/api';

interface ChatContainerProps {
  onMenuClick?: () => void;
}

export function ChatContainer({ onMenuClick }: ChatContainerProps) {
  const {
    currentConversationId,
    currentModelProvider,
    currentModelName,
    streamingMessage,
    addUserMessage,
    startStreaming,
    appendToken,
    appendThinking,
    addToolCallStart,
    updateToolCallEnd,
    finishStreaming,
    setError,
    loadModels,
  } = useChatStore();

  // Handle WebSocket messages
  const handleWebSocketMessage = useCallback(
    (event: WebSocketEvent) => {
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
        case 'message_complete':
          finishStreaming();
          break;
        case 'error':
          setError(event.data.message as string);
          finishStreaming();
          break;
      }
    },
    [appendToken, appendThinking, addToolCallStart, updateToolCallEnd, finishStreaming, setError]
  );

  const { connect, disconnect, send, isConnected, status } = useWebSocket({
    onMessage: handleWebSocketMessage,
  });

  // Connect to WebSocket when conversation changes
  useEffect(() => {
    if (currentConversationId) {
      connect(currentConversationId);
    }
    return () => {
      disconnect();
    };
  }, [currentConversationId, connect, disconnect]);

  // Load models on mount
  useEffect(() => {
    loadModels();
  }, [loadModels]);

  // Handle send message
  const handleSend = useCallback(
    (message: string) => {
      if (!currentConversationId || !isConnected) {
        setError('Not connected to server');
        return;
      }

      // Add user message to UI
      addUserMessage(message);

      // Start streaming state
      startStreaming();

      // Send message via WebSocket
      send({
        message,
        model_provider: currentModelProvider,
        model_name: currentModelName,
      });
    },
    [
      currentConversationId,
      isConnected,
      currentModelProvider,
      currentModelName,
      addUserMessage,
      startStreaming,
      send,
      setError,
    ]
  );

  // Handle stop streaming
  const handleStop = useCallback(() => {
    // TODO: Implement stop streaming
    finishStreaming();
  }, [finishStreaming]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-3 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            onClick={onMenuClick}
            className="md:hidden"
          >
            <Menu className="h-5 w-5" />
          </Button>
          <h1 className="font-semibold text-lg">Research Agent</h1>
          {/* Connection status indicator */}
          <div
            className={`w-2 h-2 rounded-full ${
              status === 'connected'
                ? 'bg-green-500'
                : status === 'connecting'
                ? 'bg-yellow-500'
                : 'bg-red-500'
            }`}
            title={`Status: ${status}`}
          />
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground hidden sm:inline">
            {currentModelName}
          </span>
          <Button variant="ghost" size="icon">
            <Settings className="h-5 w-5" />
          </Button>
        </div>
      </header>

      {/* Messages */}
      <MessageList className="flex-1" />

      {/* Input */}
      <InputArea
        onSend={handleSend}
        onStop={handleStop}
        isStreaming={!!streamingMessage}
        disabled={!isConnected}
        placeholder={isConnected ? 'Ask anything...' : 'Connecting...'}
      />
    </div>
  );
}
