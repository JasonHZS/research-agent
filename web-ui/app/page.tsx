'use client';

import dynamic from 'next/dynamic';
import { useEffect } from 'react';
import { SignedIn, SignedOut, useAuth } from '@clerk/nextjs';
import { ChatContainer } from '@/components/chat/ChatContainer';
import { FeedTicker } from '@/components/feed-ticker';
import { TodoSidebar } from '@/components/chat/TodoSidebar';
import { useChatStore } from '@/hooks/useChat';

const LoginPage = dynamic(
  () => import('@/components/login').then((mod) => mod.LoginPage),
  { ssr: false, loading: () => null },
);

export default function Home() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const { initSession, currentMessages, streamingMessage } = useChatStore();
  const hasTodos = useChatStore((s) => s.todoItems.length > 0);
  const isTodoSidebarVisible = useChatStore((s) => s.isTodoSidebarVisible);

  // Initialize session on mount for signed-in users
  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;

    const initialize = async () => {
      const token = await getToken();
      initSession(token);
    };

    void initialize();
  }, [getToken, initSession, isLoaded, isSignedIn]);

  // Check if there are any messages (hide FeedTicker when in conversation)
  const hasMessages = currentMessages.length > 0 || streamingMessage;
  const showTodoSidebar = hasTodos && isTodoSidebarVisible;

  return (
    <>
      <SignedOut>
        <LoginPage />
      </SignedOut>
      <SignedIn>
        {/* Global floating todo sidebar */}
        <TodoSidebar />
        {/* Main Chat Area - Add mobile bottom padding when todo bar is visible */}
        <main
          className={`flex-1 flex flex-col min-w-0 ${hasMessages ? '' : 'pb-[96px] sm:pb-[112px] safe-pb-feed-mobile'} ${showTodoSidebar ? 'pb-[48px] md:pb-0 safe-pb-todo-mobile' : ''}`}
        >
          <ChatContainer />
        </main>
        {/* Only show FeedTicker when no messages (welcome screen) */}
        {!hasMessages && <FeedTicker />}
      </SignedIn>
    </>
  );
}
