'use client';

import { useEffect } from 'react';
import { SignedIn, SignedOut, SignInButton, useAuth } from '@clerk/nextjs';
import { ChatContainer } from '@/components/chat/ChatContainer';
import { FeedTicker } from '@/components/feed-ticker';
import { TodoSidebar } from '@/components/chat/TodoSidebar';
import { useChatStore } from '@/hooks/useChat';

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
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center space-y-4">
            <h2 className="text-2xl font-semibold">Research Agent</h2>
            <p className="text-muted-foreground">
              Sign in to continue
            </p>
            <SignInButton mode="modal">
              <button className="px-6 py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors">
                Sign In
              </button>
            </SignInButton>
          </div>
        </div>
      </SignedOut>
      <SignedIn>
        {/* Global floating todo sidebar */}
        <TodoSidebar />
        {/* Main Chat Area - Add mobile bottom padding when todo bar is visible */}
        <main
          className={`flex-1 flex flex-col min-w-0 ${hasMessages ? '' : 'pb-[112px]'} ${showTodoSidebar ? 'md:pr-[20rem] md:pb-0 pb-[48px]' : ''}`}
        >
          <ChatContainer />
        </main>
        {/* Only show FeedTicker when no messages (welcome screen) */}
        {!hasMessages && <FeedTicker />}
      </SignedIn>
    </>
  );
}
