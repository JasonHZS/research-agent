'use client';

import { useEffect } from 'react';
import { SignedIn, SignedOut, SignInButton, useAuth } from '@clerk/nextjs';
import { ChatContainer } from '@/components/chat/ChatContainer';
import { FeedTicker } from '@/components/feed-ticker';
import { useChatStore } from '@/hooks/useChat';

export default function Home() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const { initSession } = useChatStore();

  // Initialize session on mount for signed-in users
  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;

    const initialize = async () => {
      const token = await getToken();
      initSession(token);
    };

    void initialize();
  }, [getToken, initSession, isLoaded, isSignedIn]);

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
        {/* Main Chat Area */}
        <main className="flex-1 flex flex-col min-w-0 pb-[112px]">
          <ChatContainer />
        </main>
        <FeedTicker />
      </SignedIn>
    </>
  );
}
