'use client';

import { useEffect } from 'react';
import { ChatContainer } from '@/components/chat/ChatContainer';
import { useChatStore } from '@/hooks/useChat';

export default function Home() {
  const { initSession, sessionId } = useChatStore();

  // Initialize session on mount
  useEffect(() => {
    initSession();
  }, [initSession]);

  return (
    <>
      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col min-w-0">
        <ChatContainer />
      </main>
    </>
  );
}
