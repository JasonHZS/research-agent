'use client';

import { create } from 'zustand';
import { api } from '@/lib/api';
import type { ChatMessage, ModelInfo, ToolCall, MessageSegment } from '@/lib/types';
import { generateId, getSessionId, resetSessionId } from '@/lib/utils';

/**
 * Message state for streaming responses
 */
export interface StreamingMessage {
  id: string;
  role: 'assistant';
  content: string;
  toolCalls: ToolCall[];
  /** Segments for interleaved display of tool calls and text */
  segments: MessageSegment[];
  isStreaming: boolean;
  thinkingContent?: string;
}

/**
 * Chat state interface (simplified - no conversation persistence)
 */
interface ChatState {
  // Session (ephemeral - stored in sessionStorage only)
  sessionId: string;
  currentMessages: ChatMessage[];

  // Models
  models: ModelInfo[];
  currentModelProvider: string;
  currentModelName: string;

  // Streaming state
  streamingMessage: StreamingMessage | null;

  // UI state
  isLoading: boolean;
  error: string | null;

  // Session actions
  initSession: () => void;
  newChat: () => void;

  // Model actions
  loadModels: () => Promise<void>;
  setModel: (provider: string, name: string) => void;

  // Message handling
  addUserMessage: (content: string) => void;
  startStreaming: (requestId: string) => void;
  appendToken: (content: string) => void;
  appendThinking: (content: string) => void;
  addToolCallStart: (toolCall: ToolCall) => void;
  updateToolCallEnd: (toolCall: ToolCall) => void;
  finishStreaming: () => void;
  setError: (error: string | null) => void;
  clearMessages: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  // Initial state
  sessionId: '',
  currentMessages: [],
  models: [],
  currentModelProvider: 'aliyun',
  currentModelName: 'qwen-max',
  streamingMessage: null,
  isLoading: false,
  error: null,

  // Initialize session from sessionStorage
  initSession: () => {
    const sessionId = getSessionId();
    set({ sessionId });
  },

  // Start a new chat (reset session)
  newChat: () => {
    const newSessionId = resetSessionId();
    set({
      sessionId: newSessionId,
      currentMessages: [],
      streamingMessage: null,
      error: null,
    });
  },

  // Load available models
  loadModels: async () => {
    try {
      const response = await api.getModels();
      set({
        models: response.models,
        currentModelProvider: response.current_provider,
        currentModelName: response.current_model,
      });
    } catch (error) {
      console.error('Failed to load models:', error);
    }
  },

  // Set current model
  setModel: (provider: string, name: string) => {
    set({ currentModelProvider: provider, currentModelName: name });
  },

  // Add user message to current conversation
  addUserMessage: (content: string) => {
    const { currentMessages } = get();
    const newMessage: ChatMessage = {
      id: generateId(),
      role: 'user',
      content,
      tool_calls: [],
      created_at: new Date().toISOString(),
    };
    set({ currentMessages: [...currentMessages, newMessage] });
  },

  // Start streaming a new assistant message
  startStreaming: (requestId: string) => {
    set({
      streamingMessage: {
        id: requestId,
        role: 'assistant',
        content: '',
        toolCalls: [],
        segments: [],
        isStreaming: true,
      },
    });
  },

  // Append token to streaming message
  appendToken: (content: string) => {
    const { streamingMessage } = get();
    if (streamingMessage) {
      const segments = [...streamingMessage.segments];
      const lastSegment = segments[segments.length - 1];
      
      // If no segments or last segment is tool_calls, create new text segment
      if (!lastSegment || lastSegment.type === 'tool_calls') {
        segments.push({ type: 'text', content });
      } else {
        // Append to existing text segment
        segments[segments.length - 1] = {
          ...lastSegment,
          content: lastSegment.content + content,
        };
      }
      
      set({
        streamingMessage: {
          ...streamingMessage,
          content: streamingMessage.content + content,
          segments,
        },
      });
    }
  },

  // Append thinking content
  appendThinking: (content: string) => {
    const { streamingMessage } = get();
    if (streamingMessage) {
      set({
        streamingMessage: {
          ...streamingMessage,
          thinkingContent: (streamingMessage.thinkingContent || '') + content,
        },
      });
    }
  },

  // Add tool call start
  addToolCallStart: (toolCall: ToolCall) => {
    const { streamingMessage } = get();
    if (streamingMessage) {
      const segments = [...streamingMessage.segments];
      const lastSegment = segments[segments.length - 1];
      
      // Determine if this is a new batch or same batch
      let shouldCreateNewSegment = true;
      
      if (lastSegment?.type === 'tool_calls') {
        // Check if all tools in the last segment are still running
        // If so, this is part of the same batch
        const allRunning = lastSegment.toolCalls.every(tc => tc.status === 'running');
        if (allRunning) {
          shouldCreateNewSegment = false;
        }
      }
      
      if (shouldCreateNewSegment) {
        // Create new tool_calls segment
        segments.push({ type: 'tool_calls', toolCalls: [toolCall] });
      } else {
        // Append to existing tool_calls segment (same batch)
        const lastToolCallsSegment = lastSegment as { type: 'tool_calls'; toolCalls: ToolCall[] };
        segments[segments.length - 1] = {
          ...lastToolCallsSegment,
          toolCalls: [...lastToolCallsSegment.toolCalls, toolCall],
        };
      }
      
      set({
        streamingMessage: {
          ...streamingMessage,
          toolCalls: [...streamingMessage.toolCalls, toolCall],
          segments,
        },
      });
    }
  },

  // Update tool call with result
  updateToolCallEnd: (toolCall: ToolCall) => {
    const { streamingMessage } = get();
    if (streamingMessage) {
      // Update in flat toolCalls array
      const updatedToolCalls = streamingMessage.toolCalls.map((tc) =>
        tc.id === toolCall.id ? toolCall : tc
      );
      
      // Update in segments
      const updatedSegments = streamingMessage.segments.map((segment) => {
        if (segment.type === 'tool_calls') {
          return {
            ...segment,
            toolCalls: segment.toolCalls.map((tc) =>
              tc.id === toolCall.id ? toolCall : tc
            ),
          };
        }
        return segment;
      });
      
      set({
        streamingMessage: {
          ...streamingMessage,
          toolCalls: updatedToolCalls,
          segments: updatedSegments,
        },
      });
    }
  },

  // Finish streaming and add message to conversation
  finishStreaming: () => {
    const { streamingMessage, currentMessages } = get();
    if (streamingMessage) {
      const finalMessage: ChatMessage = {
        id: streamingMessage.id,
        role: 'assistant',
        content: streamingMessage.content,
        tool_calls: streamingMessage.toolCalls,
        segments: streamingMessage.segments,
        created_at: new Date().toISOString(),
      };
      set({
        currentMessages: [...currentMessages, finalMessage],
        streamingMessage: null,
      });
    }
  },

  // Set error message
  setError: (error: string | null) => {
    set({ error, streamingMessage: null });
  },

  // Clear all messages (for new chat)
  clearMessages: () => {
    set({ currentMessages: [], streamingMessage: null, error: null });
  },
}));
