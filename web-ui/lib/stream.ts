/**
 * SSE Stream connection using Fetch + ReadableStream
 * Provides a simple interface for streaming chat responses
 */

import type { StreamEvent, ToolCall, ResearchBrief } from './types';
import { getApiBaseUrl } from './utils';

/**
 * Configuration for stream event handlers
 */
export interface StreamConfig {
  onToken: (content: string) => void;
  onThinking: (content: string) => void;
  onToolCallStart: (toolCall: ToolCall) => void;
  onToolCallEnd: (toolCall: ToolCall) => void;
  onClarification?: (question: string) => void;
  onBrief?: (brief: ResearchBrief) => void;
  onComplete: (data?: { is_clarification?: boolean }) => void;
  onError: (error: string) => void;
}

/**
 * Process a StreamEvent and call appropriate handlers
 */
function handleStreamEvent(event: StreamEvent, config: StreamConfig): void {
  switch (event.type) {
    case 'token':
      config.onToken((event.data.content as string) || '');
      break;
    case 'thinking':
      config.onThinking((event.data.content as string) || '');
      break;
    case 'tool_call_start':
      config.onToolCallStart(event.data as unknown as ToolCall);
      break;
    case 'tool_call_end':
      config.onToolCallEnd(event.data as unknown as ToolCall);
      break;
    case 'clarification':
      // Deep Research: clarification question
      config.onClarification?.((event.data.question as string) || '');
      break;
    case 'brief':
      // Deep Research: research brief
      config.onBrief?.(event.data as unknown as ResearchBrief);
      break;
    case 'message_complete':
      config.onComplete({ is_clarification: event.data.is_clarification as boolean | undefined });
      break;
    case 'error':
      config.onError((event.data.message as string) || 'Unknown error');
      break;
  }
}

/**
 * Stream a chat message using Fetch + ReadableStream
 *
 * @param sessionId - The session/conversation ID
 * @param message - The user message to send
 * @param modelProvider - The model provider (e.g., 'aliyun')
 * @param modelName - The model name (e.g., 'qwen3.5-plus')
 * @param config - Event handlers for stream events
 * @param signal - Optional AbortSignal for cancellation
 */
export async function streamChat(
  sessionId: string,
  message: string,
  modelProvider: string,
  modelName: string,
  isDeepResearch: boolean,
  config: StreamConfig,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(`${getApiBaseUrl()}/api/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      session_id: sessionId,
      message,
      model_provider: modelProvider,
      model_name: modelName,
      is_deep_research: isDeepResearch,
    }),
    signal,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`HTTP ${response.status}: ${errorText}`);
  }

  if (!response.body) {
    throw new Error('Response body is empty');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();

      if (done) {
        // Process any remaining data in buffer
        if (buffer.trim()) {
          try {
            const event = JSON.parse(buffer.trim()) as StreamEvent;
            handleStreamEvent(event, config);
          } catch {
            console.warn('Failed to parse final buffer:', buffer);
          }
        }
        break;
      }

      // Decode chunk and add to buffer
      buffer += decoder.decode(value, { stream: true });

      // Process complete NDJSON lines
      const lines = buffer.split('\n');
      buffer = lines.pop() || ''; // Keep incomplete line in buffer

      for (const line of lines) {
        if (line.trim()) {
          try {
            const event = JSON.parse(line) as StreamEvent;
            handleStreamEvent(event, config);
          } catch (e) {
            console.error('Failed to parse stream event:', line, e);
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
