'use client';

import { useCallback, useRef, useState } from 'react';
import { streamChat, type StreamConfig } from '@/lib/stream';
import type { StreamEvent, StreamingStatus, ToolCall } from '@/lib/types';

export type { StreamingStatus };

interface UseStreamOptions {
  onMessage?: (event: StreamEvent) => void;
  onError?: (error: string) => void;
}

/**
 * Hook for managing SSE stream requests (per-request model)
 *
 * Unlike WebSocket, each message creates a new HTTP request.
 * No persistent connection management needed.
 */
export function useStream(options: UseStreamOptions = {}) {
  const { onMessage, onError } = options;

  const [status, setStatus] = useState<StreamingStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  // Use refs for callbacks to avoid stale closures
  const callbacksRef = useRef({ onMessage, onError });
  callbacksRef.current = { onMessage, onError };

  /**
   * Send a message and stream the response
   */
  const sendMessage = useCallback(
    async (
      sessionId: string,
      message: string,
      modelProvider: string,
      modelName: string
    ): Promise<void> => {
      // Cancel any existing stream
      abortControllerRef.current?.abort();

      // Create new abort controller for this request
      abortControllerRef.current = new AbortController();

      setStatus('streaming');
      setError(null);

      // Create stream config that bridges to the options callbacks
      const config: StreamConfig = {
        onToken: (content) => {
          callbacksRef.current.onMessage?.({ type: 'token', data: { content } });
        },
        onThinking: (content) => {
          callbacksRef.current.onMessage?.({ type: 'thinking', data: { content } });
        },
        onToolCallStart: (toolCall) => {
          callbacksRef.current.onMessage?.({
            type: 'tool_call_start',
            data: toolCall as unknown as Record<string, unknown>,
          });
        },
        onToolCallEnd: (toolCall) => {
          callbacksRef.current.onMessage?.({
            type: 'tool_call_end',
            data: toolCall as unknown as Record<string, unknown>,
          });
        },
        onComplete: () => {
          callbacksRef.current.onMessage?.({ type: 'message_complete', data: {} });
          setStatus('idle');
        },
        onError: (errorMsg) => {
          setError(errorMsg);
          setStatus('error');
          callbacksRef.current.onError?.(errorMsg);
          callbacksRef.current.onMessage?.({ type: 'error', data: { message: errorMsg } });
        },
      };

      try {
        await streamChat(
          sessionId,
          message,
          modelProvider,
          modelName,
          config,
          abortControllerRef.current.signal
        );
      } catch (e) {
        // Ignore abort errors (user cancelled)
        if (e instanceof Error && e.name === 'AbortError') {
          setStatus('idle');
          return;
        }

        const errorMsg = e instanceof Error ? e.message : 'Unknown error';
        setError(errorMsg);
        setStatus('error');
        callbacksRef.current.onError?.(errorMsg);
      }
    },
    []
  );

  /**
   * Stop the current stream
   */
  const stopStream = useCallback(() => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    setStatus('idle');
  }, []);

  return {
    status,
    error,
    sendMessage,
    stopStream,
    isStreaming: status === 'streaming',
  };
}

// Keep the old hook name as an alias for backward compatibility
export const useWebSocket = useStream;
