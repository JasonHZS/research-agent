import { beforeEach, describe, expect, it } from 'vitest';

import { useChatStore } from './useChat';

describe('useChatStore todo sidebar state', () => {
  beforeEach(() => {
    useChatStore.setState({
      sessionId: '',
      currentMessages: [],
      models: [],
      currentModelProvider: 'aliyun',
      currentModelName: 'deepseek-v4-flash',
      isDeepResearch: false,
      canToggleDeepResearch: true,
      streamingMessage: null,
      progressNode: null,
      todoItems: [],
      isTodoSidebarVisible: false,
      isLoading: false,
      error: null,
      droppedFeedCard: null,
    });
  });

  it('keeps todo data recoverable when the sidebar is dismissed', () => {
    const todos = [
      { todo: 'Draft plan', status: 'in_progress' as const },
      { todo: 'Review results', status: 'pending' as const },
    ];

    useChatStore.getState().setTodoItems(todos);
    useChatStore.getState().hideTodoSidebar();

    const hiddenState = useChatStore.getState();
    expect(hiddenState.todoItems).toEqual(todos);
    expect(hiddenState.isTodoSidebarVisible).toBe(false);

    hiddenState.showTodoSidebar();

    const reopenedState = useChatStore.getState();
    expect(reopenedState.todoItems).toEqual(todos);
    expect(reopenedState.isTodoSidebarVisible).toBe(true);
  });

  it('re-shows the sidebar when write_todos provides a fresh plan', () => {
    const store = useChatStore.getState();

    store.hideTodoSidebar();
    store.updateToolCallEnd({
      id: 'tool-1',
      name: 'write_todos',
      args: {
        todos: [{ todo: 'Fresh task', status: 'pending' }],
      },
      status: 'completed',
    });

    const nextState = useChatStore.getState();
    expect(nextState.todoItems).toEqual([{ todo: 'Fresh task', status: 'pending' }]);
    expect(nextState.isTodoSidebarVisible).toBe(true);
  });
});
