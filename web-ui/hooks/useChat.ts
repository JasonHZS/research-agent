'use client';

import { create } from 'zustand';
import { api } from '@/lib/api';
import type { ChatMessage, ModelInfo, ToolCall, MessageSegment, ResearchBrief } from '@/lib/types';
import { generateId, getStoredSessionId, resetSessionId } from '@/lib/utils';

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
  /** Whether this is a clarification question (Deep Research mode) */
  isClarification?: boolean;
}

/**
 * Chat state interface (simplified - no conversation persistence)
 */
interface ChatState {
  // Session (ephemeral per page load; stored in sessionStorage for this tab)
  sessionId: string;
  currentMessages: ChatMessage[];

  // Models
  models: ModelInfo[];
  currentModelProvider: string;
  currentModelName: string;
  
  // Research Mode
  isDeepResearch: boolean;
  /** Whether the Deep Research toggle is still available (locked after first message if not enabled) */
  canToggleDeepResearch: boolean;

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
  toggleDeepResearch: () => void;
  /** Lock Deep Research toggle (hide the button) */
  lockDeepResearch: () => void;

  // Message handling
  addUserMessage: (content: string) => void;
  startStreaming: (requestId: string) => void;
  appendToken: (content: string) => void;
  appendThinking: (content: string) => void;
  addToolCallStart: (toolCall: ToolCall) => void;
  updateToolCallEnd: (toolCall: ToolCall) => void;
  /** Set clarification question content (Deep Research mode) */
  setClarification: (question: string) => void;
  /** Set research brief (Deep Research mode) */
  setBrief: (brief: ResearchBrief) => void;
  finishStreaming: (options?: { isClarification?: boolean }) => void;
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
  isDeepResearch: false,
  canToggleDeepResearch: true,
  streamingMessage: null,
  isLoading: false,
  error: null,

  // Initialize session on page load, clearing any stale backend state
  initSession: () => {
    const { sessionId: currentSessionId } = get();
    if (currentSessionId) {
      return;
    }

    const existingSessionId = getStoredSessionId();
    if (existingSessionId) {
      void api.resetSession(existingSessionId).catch((error) => {
        console.warn('Failed to reset session:', error);
      });
    }

    const sessionId = resetSessionId();
    set({
      sessionId,
      currentMessages: [],
      streamingMessage: null,
      error: null,
    });
  },

  // Start a new chat (reset session)
  newChat: () => {
    const { sessionId } = get();
    if (sessionId) {
      void api.resetSession(sessionId).catch((error) => {
        console.warn('Failed to reset session:', error);
      });
    }

    const newSessionId = resetSessionId();
    set({
      sessionId: newSessionId,
      currentMessages: [],
      streamingMessage: null,
      error: null,
      // Reset Deep Research state for new chat
      isDeepResearch: false,
      canToggleDeepResearch: true,
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

  // Toggle Deep Research mode
  toggleDeepResearch: () => {
    set((state) => ({ isDeepResearch: !state.isDeepResearch }));
  },

  // Lock Deep Research toggle (hide the button permanently for this session)
  lockDeepResearch: () => {
    set({ canToggleDeepResearch: false });
  },

  // Add user message to current conversation
  addUserMessage: (content: string) => {
    const { currentMessages, isDeepResearch, canToggleDeepResearch } = get();
    const newMessage: ChatMessage = {
      id: generateId(),
      role: 'user',
      content,
      tool_calls: [],
      created_at: new Date().toISOString(),
    };
    
    // Lock Deep Research toggle if not enabled and still unlocked
    const updates: Partial<ChatState> = {
      currentMessages: [...currentMessages, newMessage],
    };
    if (!isDeepResearch && canToggleDeepResearch) {
      updates.canToggleDeepResearch = false;
    }
    
    set(updates);
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

  // Add tool call start - append chronologically
  addToolCallStart: (toolCall: ToolCall) => {
    const { streamingMessage } = get();
    if (streamingMessage) {
      const segments = [...streamingMessage.segments];
      const lastSegment = segments[segments.length - 1];

      // Chronological append:
      // - If last segment is tool_calls with all running status, add to it (batch)
      // - Otherwise create a new tool_calls segment at the end
      if (lastSegment?.type === 'tool_calls') {
        const allRunning = lastSegment.toolCalls.every(tc => tc.status === 'running');
        if (allRunning) {
          // Batch with the current tool_calls segment
          segments[segments.length - 1] = {
            ...lastSegment,
            toolCalls: [...lastSegment.toolCalls, toolCall],
          };
        } else {
          // Previous tool calls completed, start a new segment
          segments.push({ type: 'tool_calls', toolCalls: [toolCall] });
        }
      } else {
        // Last segment is text or empty, append new tool_calls segment
        segments.push({ type: 'tool_calls', toolCalls: [toolCall] });
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

  // Set clarification question (Deep Research mode)
  setClarification: (question: string) => {
    const { streamingMessage } = get();
    if (streamingMessage) {
      // Preserve existing tool call segments, append clarification text
      const segments = [...streamingMessage.segments];
      const lastSegment = segments[segments.length - 1];

      if (!lastSegment) {
        segments.push({ type: 'text', content: question });
      } else if (lastSegment.type === 'text') {
        segments[segments.length - 1] = {
          ...lastSegment,
          content: question,
        };
      } else {
        segments.push({ type: 'text', content: question });
      }

      set({
        streamingMessage: {
          ...streamingMessage,
          content: question,
          segments,
          isClarification: true,
        },
      });
    }
  },

  // Set research brief (Deep Research mode)
  setBrief: (brief: ResearchBrief) => {
    const { streamingMessage } = get();
    if (streamingMessage) {
      // Format brief as markdown
      const sectionsText = brief.sections
        .map((s, i) => `### ${i + 1}. ${s.title}\n\n${s.description}`)
        .join('\n\n');
      
      const briefContent = `## 研究大纲\n\n${sectionsText}`;
      
      // Append brief to existing content or create new
      const newContent = streamingMessage.content 
        ? `${streamingMessage.content}\n\n${briefContent}`
        : briefContent;
      
      // Update segments
      const segments = [...streamingMessage.segments];
      const lastSegment = segments[segments.length - 1];
      
      if (!lastSegment || lastSegment.type === 'tool_calls') {
        segments.push({ type: 'text', content: briefContent });
      } else {
        segments[segments.length - 1] = {
          ...lastSegment,
          content: lastSegment.content + '\n\n' + briefContent,
        };
      }
      
      set({
        streamingMessage: {
          ...streamingMessage,
          content: newContent,
          segments,
        },
      });
    }
  },

  // Finish streaming and add message to conversation
  finishStreaming: (options?: { isClarification?: boolean }) => {
    const { streamingMessage, currentMessages } = get();
    if (streamingMessage) {
      // Determine if this is a clarification message
      const isClarification = options?.isClarification ?? streamingMessage.isClarification;
      
      const finalMessage: ChatMessage = {
        id: streamingMessage.id,
        role: 'assistant',
        content: streamingMessage.content,
        tool_calls: streamingMessage.toolCalls,
        segments: streamingMessage.segments,
        isClarification,
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
