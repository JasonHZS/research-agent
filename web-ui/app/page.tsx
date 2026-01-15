'use client';

import { useEffect, useState } from 'react';
import { Sidebar } from '@/components/sidebar/Sidebar';
import { ChatContainer } from '@/components/chat/ChatContainer';
import { useChatStore } from '@/hooks/useChat';

export default function Home() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const { loadConversations, currentConversationId, createConversation } = useChatStore();

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  // Create a new conversation if none exists
  useEffect(() => {
    if (!currentConversationId) {
      createConversation();
    }
  }, [currentConversationId, createConversation]);

  return (
    <>
      {/* Sidebar */}
      <Sidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
      />

      {/* Main Chat Area */}
      <main className="flex-1 flex flex-col min-w-0">
        <ChatContainer onMenuClick={() => setSidebarOpen(!sidebarOpen)} />
      </main>
    </>
  );
}
