/**
 * Shared type definitions for the Research Agent frontend
 * These types are designed to be transport-agnostic (WebSocket/SSE)
 */

/**
 * Status of a tool call
 */
export type ToolCallStatus = 'running' | 'completed' | 'failed';

/**
 * Tool call information
 */
export interface ToolCall {
  id: string;
  name: string;
  args: Record<string, unknown>;
  result?: unknown;
  status: ToolCallStatus;
}

/**
 * Message segment types for interleaved display
 * Segments allow tool calls and text to be displayed in chronological order
 */
export type MessageSegmentType = 'text' | 'tool_calls';

/**
 * A text segment containing markdown content
 */
export interface TextSegment {
  type: 'text';
  content: string;
}

/**
 * A tool calls segment containing a batch of tool calls
 */
export interface ToolCallsSegment {
  type: 'tool_calls';
  toolCalls: ToolCall[];
}

/**
 * A message segment - either text or tool calls
 */
export type MessageSegment = TextSegment | ToolCallsSegment;

/**
 * Role of a message in the conversation
 */
export type MessageRole = 'user' | 'assistant' | 'system';

/**
 * A single chat message
 */
export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  tool_calls: ToolCall[];
  /** Segments for interleaved display (optional for backward compatibility) */
  segments?: MessageSegment[];
  /** Whether this message is a clarification question (Deep Research mode) */
  isClarification?: boolean;
  created_at: string;
}

/**
 * Information about an available model
 */
export interface ModelInfo {
  provider: string;
  name: string;
  display_name: string;
  supports_thinking: boolean;
}

/**
 * Types of streaming events (transport-agnostic naming)
 */
export type StreamEventType =
  | 'token'
  | 'thinking'
  | 'tool_call_start'
  | 'tool_call_end'
  | 'message_complete'
  | 'error'
  | 'clarification'  // Deep Research 澄清问题
  | 'brief';  // Deep Research 研究大纲

/**
 * Section plan in research brief
 */
export interface SectionPlan {
  title: string;
  description: string;
}

/**
 * Research brief data from Deep Research mode
 */
export interface ResearchBrief {
  research_brief: string;
  sections: SectionPlan[];
}

/**
 * A streaming event from the server
 */
export interface StreamEvent {
  type: StreamEventType;
  data: Record<string, unknown>;
}

/**
 * Streaming status (simplified for SSE per-request model)
 */
export type StreamingStatus = 'idle' | 'streaming' | 'error';
