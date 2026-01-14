'use client';

import { create } from 'zustand';
import { api, type ChatMessage, type ConversationSummary, type ModelInfo, type ToolCall } from '@/lib/api';
import { generateId } from '@/lib/utils';

// Message state for streaming
export interface StreamingMessage {
  id: string;
  role: 'assistant';
  content: string;
  toolCalls: ToolCall[];
  isStreaming: boolean;
  thinkingContent?: string;
}

interface ChatState {
  // Conversations
  conversations: ConversationSummary[];
  currentConversationId: string | null;
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

  // Actions
  loadConversations: () => Promise<void>;
  loadConversation: (id: string) => Promise<void>;
  createConversation: (title?: string) => Promise<string>;
  deleteConversation: (id: string) => Promise<void>;
  setCurrentConversation: (id: string) => void;

  loadModels: () => Promise<void>;
  setModel: (provider: string, name: string) => void;

  // Message handling
  addUserMessage: (content: string) => void;
  startStreaming: () => void;
  appendToken: (content: string) => void;
  appendThinking: (content: string) => void;
  addToolCallStart: (toolCall: ToolCall) => void;
  updateToolCallEnd: (toolCall: ToolCall) => void;
  finishStreaming: () => void;
  setError: (error: string | null) => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  // Initial state
  conversations: [],
  currentConversationId: null,
  currentMessages: [],
  models: [],
  currentModelProvider: 'aliyun',
  currentModelName: 'qwen-max',
  streamingMessage: null,
  isLoading: false,
  error: null,

  // Load all conversations
  loadConversations: async () => {
    try {
      set({ isLoading: true, error: null });
      const conversations = await api.getConversations();
      set({ conversations, isLoading: false });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to load conversations',
        isLoading: false,
      });
    }
  },

  // Load a specific conversation with messages
  loadConversation: async (id: string) => {
    try {
      set({ isLoading: true, error: null });
      const conversation = await api.getConversation(id);
      set({
        currentConversationId: id,
        currentMessages: conversation.messages,
        currentModelProvider: conversation.model_provider,
        currentModelName: conversation.model_name,
        isLoading: false,
      });
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to load conversation',
        isLoading: false,
      });
    }
  },

  // Create a new conversation
  createConversation: async (title?: string) => {
    try {
      set({ isLoading: true, error: null });
      const { currentModelProvider, currentModelName } = get();
      const conversation = await api.createConversation({
        title,
        model_provider: currentModelProvider,
        model_name: currentModelName,
      });
      const conversations = await api.getConversations();
      set({
        conversations,
        currentConversationId: conversation.id,
        currentMessages: [],
        isLoading: false,
      });
      return conversation.id;
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to create conversation',
        isLoading: false,
      });
      return '';
    }
  },

  // Delete a conversation
  deleteConversation: async (id: string) => {
    try {
      await api.deleteConversation(id);
      const { currentConversationId, conversations } = get();
      const newConversations = conversations.filter((c) => c.id !== id);
      set({ conversations: newConversations });

      // If deleted current conversation, switch to another or create new
      if (currentConversationId === id) {
        if (newConversations.length > 0) {
          get().loadConversation(newConversations[0].id);
        } else {
          set({ currentConversationId: null, currentMessages: [] });
        }
      }
    } catch (error) {
      set({
        error: error instanceof Error ? error.message : 'Failed to delete conversation',
      });
    }
  },

  // Set current conversation without loading
  setCurrentConversation: (id: string) => {
    set({ currentConversationId: id });
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
  startStreaming: () => {
    set({
      streamingMessage: {
        id: generateId(),
        role: 'assistant',
        content: '',
        toolCalls: [],
        isStreaming: true,
      },
    });
  },

  // Append token to streaming message
  appendToken: (content: string) => {
    const { streamingMessage } = get();
    if (streamingMessage) {
      set({
        streamingMessage: {
          ...streamingMessage,
          content: streamingMessage.content + content,
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
      set({
        streamingMessage: {
          ...streamingMessage,
          toolCalls: [...streamingMessage.toolCalls, toolCall],
        },
      });
    }
  },

  // Update tool call with result
  updateToolCallEnd: (toolCall: ToolCall) => {
    const { streamingMessage } = get();
    if (streamingMessage) {
      const updatedToolCalls = streamingMessage.toolCalls.map((tc) =>
        tc.id === toolCall.id ? toolCall : tc
      );
      set({
        streamingMessage: {
          ...streamingMessage,
          toolCalls: updatedToolCalls,
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
        created_at: new Date().toISOString(),
      };
      set({
        currentMessages: [...currentMessages, finalMessage],
        streamingMessage: null,
      });

      // Refresh conversation list to update titles
      get().loadConversations();
    }
  },

  // Set error message
  setError: (error: string | null) => {
    set({ error, streamingMessage: null });
  },
}));
