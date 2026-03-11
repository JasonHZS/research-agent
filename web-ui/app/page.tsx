'use client';

import { useEffect } from 'react';
import { SignedIn, SignedOut, SignInButton, useAuth } from '@clerk/nextjs';
import { ChatContainer } from '@/components/chat/ChatContainer';
import { FeedTicker } from '@/components/feed-ticker';
import { useChatStore } from '@/hooks/useChat';

export default function Home() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const { initSession, currentMessages, streamingMessage } = useChatStore();

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

  return (
    <>
      <SignedOut>
        <div className="flex-1 flex items-center justify-center px-4">
          <div className="text-center space-y-4 max-w-sm w-full">
            <h2 className="text-xl sm:text-2xl font-semibold">Research Agent</h2>
            <p className="text-muted-foreground text-sm sm:text-base">
              Sign in to continue
            </p>
            <SignInButton mode="modal">
              <button className="w-full sm:w-auto px-6 py-3 sm:py-2 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors touch-manipulation min-h-[44px]">
                Sign In
              </button>
            </SignInButton>
          </div>
        </div>
      </SignedOut>
      <SignedIn>
        {/* Main Chat Area - Remove bottom padding when in conversation */}
        <main className={`flex-1 flex flex-col min-w-0 ${hasMessages ? '' : 'pb-[100px] sm:pb-[112px]'}`}>
          <ChatContainer />
        </main>
        {/* Only show FeedTicker when no messages (welcome screen) */}
        {!hasMessages && <FeedTicker />}
      </SignedIn>
    </>
  );
}
