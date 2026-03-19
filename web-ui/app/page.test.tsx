import React from 'react';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import Home from './page';

const getTokenMock = vi.fn();
let mockChatState: {
  initSession: ReturnType<typeof vi.fn>;
  currentMessages: Array<{ id: string }>;
  streamingMessage: null | { id: string };
  todoItems: Array<{ todo: string; status: 'pending' | 'in_progress' | 'completed' }>;
  isTodoSidebarVisible: boolean;
};

vi.mock('@clerk/nextjs', () => ({
  SignedIn: ({ children }: { children: React.ReactNode }) => React.createElement(React.Fragment, null, children),
  SignedOut: () => null,
  SignInButton: ({ children }: { children: React.ReactNode }) => React.createElement(React.Fragment, null, children),
  useAuth: () => ({
    getToken: getTokenMock,
    isLoaded: true,
    isSignedIn: true,
  }),
}));

vi.mock('@/components/chat/ChatContainer', () => ({
  ChatContainer: () => React.createElement('div', { 'data-testid': 'chat-container' }),
}));

vi.mock('@/components/feed-ticker', () => ({
  FeedTicker: () => React.createElement('div', { 'data-testid': 'feed-ticker' }),
}));

vi.mock('@/components/chat/TodoSidebar', () => ({
  TodoSidebar: () => React.createElement('div', { 'data-testid': 'todo-sidebar' }),
}));

vi.mock('@/hooks/useChat', () => ({
  useChatStore: (selector?: (state: typeof mockChatState) => unknown) =>
    selector ? selector(mockChatState) : mockChatState,
}));

describe('Home todo layout', () => {
  beforeEach(() => {
    getTokenMock.mockResolvedValue('token-1');
    mockChatState = {
      initSession: vi.fn(),
      currentMessages: [{ id: 'message-1' }],
      streamingMessage: null,
      todoItems: [],
      isTodoSidebarVisible: false,
    };
  });

  it('reserves desktop space when the todo sidebar is visible', () => {
    mockChatState.todoItems = [{ todo: 'Draft plan', status: 'pending' }];
    mockChatState.isTodoSidebarVisible = true;

    render(React.createElement(Home));

    expect(screen.getByRole('main')).toHaveClass('md:pr-[20rem]');
    expect(screen.getByRole('main')).toHaveClass('pb-[48px]');
  });

  it('does not reserve desktop space when the todo sidebar is hidden', () => {
    mockChatState.todoItems = [{ todo: 'Draft plan', status: 'pending' }];
    mockChatState.isTodoSidebarVisible = false;

    render(React.createElement(Home));

    expect(screen.getByRole('main')).not.toHaveClass('md:pr-[20rem]');
    expect(screen.getByRole('main')).not.toHaveClass('pb-[48px]');
  });
});
