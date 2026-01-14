'use client';

import { useCallback, useRef, useState } from 'react';
import { getWsBaseUrl } from '@/lib/utils';
import type { WebSocketEvent } from '@/lib/api';

export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

interface UseWebSocketOptions {
  onMessage?: (event: WebSocketEvent) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  reconnectAttempts?: number;
  reconnectInterval?: number;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const {
    onMessage,
    onOpen,
    onClose,
    onError,
    reconnectAttempts = 3,
    reconnectInterval = 2000,
  } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout>>();

  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [error, setError] = useState<string | null>(null);

  const cleanup = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current.onmessage = null;
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const connect = useCallback(
    (conversationId: string) => {
      cleanup();
      setStatus('connecting');
      setError(null);

      const wsUrl = `${getWsBaseUrl()}/api/chat/ws/${conversationId}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus('connected');
        reconnectCountRef.current = 0;
        onOpen?.();
      };

      ws.onclose = () => {
        setStatus('disconnected');
        onClose?.();

        // Auto reconnect
        if (reconnectCountRef.current < reconnectAttempts) {
          reconnectCountRef.current++;
          reconnectTimeoutRef.current = setTimeout(() => {
            connect(conversationId);
          }, reconnectInterval);
        }
      };

      ws.onerror = (event) => {
        setStatus('error');
        setError('WebSocket connection error');
        onError?.(event);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as WebSocketEvent;
          onMessage?.(data);
        } catch (e) {
          console.error('Failed to parse WebSocket message:', e);
        }
      };
    },
    [cleanup, onMessage, onOpen, onClose, onError, reconnectAttempts, reconnectInterval]
  );

  const disconnect = useCallback(() => {
    reconnectCountRef.current = reconnectAttempts; // Prevent reconnect
    cleanup();
    setStatus('disconnected');
  }, [cleanup, reconnectAttempts]);

  const send = useCallback(
    (data: Record<string, unknown>) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify(data));
        return true;
      }
      return false;
    },
    []
  );

  return {
    status,
    error,
    connect,
    disconnect,
    send,
    isConnected: status === 'connected',
  };
}
