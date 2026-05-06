/**
 * SSE stream connection using Fetch + ReadableStream.
 * We keep fetch instead of EventSource because this endpoint uses POST and
 * Authorization headers, but the payload framing is standard SSE.
 */

import type { StreamEvent, ToolCall, ResearchBrief, StreamingSnapshot } from './types';
import { getApiBaseUrl } from './utils';

export class StreamRequestError extends Error {
  status?: number;

  constructor(message: string, status?: number) {
    super(message);
    this.name = 'StreamRequestError';
    this.status = status;
  }
}

/**
 * Configuration for stream event handlers
 */
export interface StreamConfig {
  onSnapshot?: (snapshot: StreamingSnapshot) => void;
  onToken: (content: string) => void;
  onThinking: (content: string) => void;
  onToolCallStart: (toolCall: ToolCall) => void;
  onToolCallEnd: (toolCall: ToolCall) => void;
  onClarification?: (question: string) => void;
  onBrief?: (brief: ResearchBrief) => void;
  onProgress?: (node: string) => void;
  onComplete: (data?: { is_clarification?: boolean }) => void;
  onError: (error: string) => void;
}

/**
 * Process a StreamEvent and call appropriate handlers
 */
function handleStreamEvent(event: StreamEvent, config: StreamConfig): void {
  switch (event.type) {
    case 'snapshot':
      config.onSnapshot?.(event.data as unknown as StreamingSnapshot);
      break;
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
    case 'progress':
      // Deep Research: node progress heartbeat
      config.onProgress?.((event.data.node as string) || '');
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
 * Parse a single SSE frame into a transport-agnostic StreamEvent.
 * Comment-only frames return null and should be ignored by the caller.
 */
function parseSseFrame(frame: string): StreamEvent | null {
  const lines = frame.split(/\r?\n/);
  let eventType: string | null = null;
  const dataLines: string[] = [];

  for (const line of lines) {
    if (!line) {
      continue;
    }

    if (line.startsWith(':')) {
      continue;
    }

    const separatorIndex = line.indexOf(':');
    const field = separatorIndex >= 0 ? line.slice(0, separatorIndex) : line;
    let value = separatorIndex >= 0 ? line.slice(separatorIndex + 1) : '';
    if (value.startsWith(' ')) {
      value = value.slice(1);
    }

    switch (field) {
      case 'event':
        eventType = value;
        break;
      case 'data':
        dataLines.push(value);
        break;
      default:
        break;
    }
  }

  if (!eventType) {
    return null;
  }

  const rawData = dataLines.join('\n');
  let data: Record<string, unknown> = {};

  if (rawData) {
    data = JSON.parse(rawData) as Record<string, unknown>;
  }

  return {
    type: eventType as StreamEvent['type'],
    data,
  };
}

/**
 * Stream a chat message using Fetch + ReadableStream
 *
 * @param sessionId - The session/conversation ID
 * @param message - The user message to send
 * @param modelProvider - The model provider (e.g., 'aliyun')
 * @param modelName - The model name (e.g., 'deepseek-v4-flash')
 * @param config - Event handlers for stream events
 * @param signal - Optional AbortSignal for cancellation
 */
async function openSseStream(
  input: RequestInfo | URL,
  init: RequestInit,
  config: StreamConfig,
): Promise<void> {
  const response = await fetch(input, init);

  if (!response.ok) {
    const errorText = await response.text();
    throw new StreamRequestError(
      `HTTP ${response.status}: ${errorText}`,
      response.status,
    );
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
        const finalFrame = buffer.trim();
        if (finalFrame) {
          try {
            const event = parseSseFrame(finalFrame);
            if (event) {
              handleStreamEvent(event, config);
            }
          } catch {
            console.warn('Failed to parse final SSE frame:', finalFrame);
          }
        }
        break;
      }

      buffer += decoder.decode(value, { stream: true });

      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = frames.pop() || '';

      for (const frame of frames) {
        const trimmedFrame = frame.trim();
        if (trimmedFrame) {
          try {
            const event = parseSseFrame(trimmedFrame);
            if (event) {
              handleStreamEvent(event, config);
            }
          } catch (e) {
            console.error('Failed to parse SSE frame:', trimmedFrame, e);
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

export async function streamChat(
  sessionId: string,
  message: string,
  requestId: string,
  modelProvider: string,
  modelName: string,
  isDeepResearch: boolean,
  config: StreamConfig,
  signal?: AbortSignal,
  token?: string | null
): Promise<void> {
  const headers: Record<string, string> = {
    'Accept': 'text/event-stream',
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  await openSseStream(
    `${getApiBaseUrl()}/api/chat/stream`,
    {
      method: 'POST',
      headers,
      body: JSON.stringify({
        session_id: sessionId,
        message,
        request_id: requestId,
        model_provider: modelProvider,
        model_name: modelName,
        is_deep_research: isDeepResearch,
      }),
      signal,
    },
    config,
  );
}

export async function resumeChatStream(
  sessionId: string,
  config: StreamConfig,
  signal?: AbortSignal,
  token?: string | null,
): Promise<void> {
  const headers: Record<string, string> = {
    'Accept': 'text/event-stream',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  await openSseStream(
    `${getApiBaseUrl()}/api/chat/stream/${encodeURIComponent(sessionId)}`,
    {
      method: 'GET',
      headers,
      signal,
    },
    config,
  );
}
