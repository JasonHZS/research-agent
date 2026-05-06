import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { StreamRequestError } from '@/lib/stream';
import { ChatContainer } from './ChatContainer';

const getTokenMock = vi.fn();
const sendMessageMock = vi.fn();
const resumeStreamMock = vi.fn();
const stopStreamMock = vi.fn();

const loadModelsMock = vi.fn();
const addUserMessageMock = vi.fn();
const startStreamingMock = vi.fn();
const setErrorMock = vi.fn();
const newChatMock = vi.fn();
const clearDroppedFeedCardMock = vi.fn();
const finishStreamingMock = vi.fn();
const appendTokenMock = vi.fn();
const appendThinkingMock = vi.fn();
const addToolCallStartMock = vi.fn();
const updateToolCallEndMock = vi.fn();
const setClarificationMock = vi.fn();
const setBriefMock = vi.fn();
const setProgressNodeMock = vi.fn();
const hydrateStreamingMock = vi.fn();
const toggleDeepResearchMock = vi.fn();
const lockDeepResearchMock = vi.fn();
const setDroppedFeedCardMock = vi.fn();

vi.mock('@clerk/nextjs', () => ({
  useAuth: () => ({
    getToken: getTokenMock,
  }),
  UserButton: () => React.createElement('div', { 'data-testid': 'user-button' }),
}));

vi.mock('@/hooks/useWebSocket', () => ({
  useStream: () => ({
    sendMessage: sendMessageMock,
    resumeStream: resumeStreamMock,
    stopStream: stopStreamMock,
    isStreaming: false,
    status: 'idle',
  }),
}));

const useChatStoreMock = vi.fn();
vi.mock('@/hooks/useChat', () => ({
  useChatStore: () => useChatStoreMock(),
}));

vi.mock('./MessageList', () => ({
  MessageList: () => React.createElement('div', { 'data-testid': 'message-list' }),
}));

vi.mock('./InputArea', () => ({
  InputArea: ({ onSend }: { onSend: (message: string) => void }) =>
    React.createElement(
      'button',
      {
        type: 'button',
        onClick: () => onSend('new prompt'),
      },
      'send',
    ),
}));

function createStoreState() {
  return {
    sessionId: 'session-1',
    currentModelProvider: 'aliyun',
    currentModelName: 'deepseek-v4-flash',
    currentMessages: [],
    streamingMessage: null,
    isLoading: false,
    addUserMessage: addUserMessageMock,
    startStreaming: startStreamingMock,
    appendToken: appendTokenMock,
    appendThinking: appendThinkingMock,
    addToolCallStart: addToolCallStartMock,
    updateToolCallEnd: updateToolCallEndMock,
    setClarification: setClarificationMock,
    setBrief: setBriefMock,
    setProgressNode: setProgressNodeMock,
    hydrateStreaming: hydrateStreamingMock,
    finishStreaming: finishStreamingMock,
    setError: setErrorMock,
    loadModels: loadModelsMock,
    newChat: newChatMock,
    isDeepResearch: false,
    toggleDeepResearch: toggleDeepResearchMock,
    canToggleDeepResearch: true,
    lockDeepResearch: lockDeepResearchMock,
    droppedFeedCard: null,
    setDroppedFeedCard: setDroppedFeedCardMock,
    clearDroppedFeedCard: clearDroppedFeedCardMock,
  };
}

describe('ChatContainer recovery fallback', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getTokenMock.mockResolvedValue('token-1');
    useChatStoreMock.mockReturnValue(createStoreState());
  });

  it('does not resume an older background run after POST 409', async () => {
    sendMessageMock.mockRejectedValue(
      new StreamRequestError('HTTP 409: already has an active run', 409),
    );

    render(React.createElement(ChatContainer));

    fireEvent.click(screen.getByRole('button', { name: 'send' }));

    await waitFor(() => {
      expect(addUserMessageMock).toHaveBeenCalledWith('new prompt', undefined);
    });

    expect(startStreamingMock).toHaveBeenCalledTimes(1);
    expect(resumeStreamMock).not.toHaveBeenCalled();
    expect(setErrorMock).toHaveBeenCalledWith('HTTP 409: already has an active run');
    expect(newChatMock).not.toHaveBeenCalled();
  });

  it('preserves local chat state when send and resume both fail', async () => {
    sendMessageMock.mockRejectedValue(new Error('network down'));
    resumeStreamMock.mockRejectedValue(new Error('resume failed'));

    render(React.createElement(ChatContainer));

    fireEvent.click(screen.getByRole('button', { name: 'send' }));

    await waitFor(() => {
      expect(resumeStreamMock).toHaveBeenCalledWith('session-1', 'token-1');
    });

    expect(addUserMessageMock).toHaveBeenCalledWith('new prompt', undefined);
    expect(startStreamingMock).toHaveBeenCalledTimes(1);
    expect(setErrorMock).toHaveBeenCalledWith('resume failed');
    expect(newChatMock).not.toHaveBeenCalled();
  });

  it('attempts resume when POST fails with a retryable error', async () => {
    sendMessageMock.mockRejectedValue(
      new StreamRequestError('HTTP 503: upstream unavailable', 503),
    );
    resumeStreamMock.mockResolvedValue(undefined);

    render(React.createElement(ChatContainer));

    fireEvent.click(screen.getByRole('button', { name: 'send' }));

    await waitFor(() => {
      expect(resumeStreamMock).toHaveBeenCalledWith('session-1', 'token-1');
    });

    expect(addUserMessageMock).toHaveBeenCalledWith('new prompt', undefined);
    expect(startStreamingMock).toHaveBeenCalledTimes(1);
    expect(setErrorMock).not.toHaveBeenCalled();
    expect(newChatMock).not.toHaveBeenCalled();
  });
});
