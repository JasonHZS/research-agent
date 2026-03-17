'use client';

import { useCallback, useRef, useState } from 'react';
import { StreamRequestError, resumeChatStream, streamChat, type StreamConfig } from '@/lib/stream';
import type { StreamEvent, StreamingStatus } from '@/lib/types';
import { getStreamRecoveryConfig } from '@/lib/utils';

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

  const sleep = useCallback((delayMs: number, signal: AbortSignal) => {
    return new Promise<void>((resolve, reject) => {
      const createAbortError = () => {
        const error = new Error('The operation was aborted');
        error.name = 'AbortError';
        return error;
      };

      if (signal.aborted) {
        reject(createAbortError());
        return;
      }

      const timeoutId = window.setTimeout(() => {
        signal.removeEventListener('abort', onAbort);
        resolve();
      }, delayMs);

      const onAbort = () => {
        window.clearTimeout(timeoutId);
        signal.removeEventListener('abort', onAbort);
        reject(createAbortError());
      };

      signal.addEventListener('abort', onAbort, { once: true });
    });
  }, []);

  const isRetryableResumeError = useCallback((error: unknown): boolean => {
    if (!(error instanceof Error)) {
      return false;
    }

    if (error.name === 'AbortError') {
      return false;
    }

    if (error instanceof StreamRequestError && error.status !== undefined) {
      if (error.status === 404 || error.status === 409) {
        return false;
      }

      return error.status === 408 || error.status === 429 || error.status >= 500;
    }

    return true;
  }, []);

  const createStreamConfig = useCallback((): StreamConfig => ({
    onSnapshot: (snapshot) => {
      callbacksRef.current.onMessage?.({
        type: 'snapshot',
        data: snapshot as unknown as Record<string, unknown>,
      });
    },
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
    onClarification: (question) => {
      callbacksRef.current.onMessage?.({ type: 'clarification', data: { question } });
    },
    onBrief: (brief) => {
      callbacksRef.current.onMessage?.({ type: 'brief', data: brief as unknown as Record<string, unknown> });
    },
    onProgress: (node) => {
      callbacksRef.current.onMessage?.({ type: 'progress', data: { node } });
    },
    onComplete: (data) => {
      callbacksRef.current.onMessage?.({
        type: 'message_complete',
        data: { is_clarification: data?.is_clarification },
      });
      setStatus('idle');
    },
    onError: (errorMsg) => {
      setError(errorMsg);
      setStatus('error');
      callbacksRef.current.onError?.(errorMsg);
      callbacksRef.current.onMessage?.({ type: 'error', data: { message: errorMsg } });
    },
  }), []);

  /**
   * Send a message and stream the response
   */
  const sendMessage = useCallback(
    async (
      sessionId: string,
      message: string,
      requestId: string,
      modelProvider: string,
      modelName: string,
      isDeepResearch: boolean,
      token?: string | null
    ): Promise<void> => {
      // Cancel any existing stream
      abortControllerRef.current?.abort();

      // Create new abort controller for this request
      abortControllerRef.current = new AbortController();

      setStatus('streaming');
      setError(null);

      try {
        await streamChat(
          sessionId,
          message,
          requestId,
          modelProvider,
          modelName,
          isDeepResearch,
          createStreamConfig(),
          abortControllerRef.current.signal,
          token
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
        throw e;
      }
    },
    [createStreamConfig]
  );

  const resumeStream = useCallback(
    async (
      sessionId: string,
      token?: string | null
    ): Promise<void> => {
      const recoveryConfig = getStreamRecoveryConfig();
      if (recoveryConfig.maxResumeAttempts <= 0) {
        const error = new Error('Automatic stream resume is disabled');
        setError(error.message);
        setStatus('error');
        callbacksRef.current.onError?.(error.message);
        throw error;
      }

      let attempt = 0;
      let currentDelayMs = recoveryConfig.baseRetryDelayMs;

      while (attempt < recoveryConfig.maxResumeAttempts) {
        abortControllerRef.current?.abort();
        abortControllerRef.current = new AbortController();

        setStatus('streaming');
        setError(null);

        try {
          await resumeChatStream(
            sessionId,
            createStreamConfig(),
            abortControllerRef.current.signal,
            token,
          );
          return;
        } catch (e) {
          if (e instanceof Error && e.name === 'AbortError') {
            setStatus('idle');
            return;
          }

          attempt += 1;
          const errorMsg = e instanceof Error ? e.message : 'Unknown error';

          if (
            attempt >= recoveryConfig.maxResumeAttempts ||
            !isRetryableResumeError(e)
          ) {
            setError(errorMsg);
            setStatus('error');
            callbacksRef.current.onError?.(errorMsg);
            throw e;
          }

          try {
            await sleep(currentDelayMs, abortControllerRef.current.signal);
          } catch (sleepError) {
            if (sleepError instanceof Error && sleepError.name === 'AbortError') {
              setStatus('idle');
              return;
            }
            throw sleepError;
          }
          currentDelayMs = Math.min(
            recoveryConfig.maxRetryDelayMs,
            Math.max(
              recoveryConfig.baseRetryDelayMs,
              Math.round(currentDelayMs * recoveryConfig.backoffMultiplier)
            )
          );
        }
      }
    },
    [createStreamConfig, isRetryableResumeError, sleep]
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
    resumeStream,
    stopStream,
    isStreaming: status === 'streaming',
  };
}

// Keep the old hook name as an alias for backward compatibility
export const useWebSocket = useStream;
