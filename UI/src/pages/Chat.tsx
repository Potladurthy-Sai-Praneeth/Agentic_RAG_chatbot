import React, { useState, useEffect, useRef } from 'react';
import { useAppDispatch } from '@/hooks/useAppDispatch';
import { useAppSelector } from '@/hooks/useAppSelector';
import { sendMessage, createNewSession, updateSessionTitle } from '@/store/chatSlice';
import { Sidebar } from '@/components/Sidebar';
import { ChatMessage } from '@/components/ChatMessage';
import { ChatInput } from '@/components/ChatInput';
import { EmptyState } from '@/components/EmptyState';
import { Menu, AlertCircle } from 'lucide-react';
import { apiService } from '@/services/api';

export const Chat: React.FC = () => {
  const dispatch = useAppDispatch();
  const { currentSessionId, messages, sending, error } = useAppSelector((state) => state.chat);

  const [sidebarOpen, setSidebarOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Auto-scroll to bottom when new messages arrive
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const generateUUID = () => {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = Math.random() * 16 | 0;
      const v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  };

  const handleSendMessage = async (content: string) => {
    const messageId = generateUUID();
    const timestamp = new Date().toISOString();

    if (!currentSessionId) {
      // Create a new session if none exists
      const result = await dispatch(createNewSession());
      if (createNewSession.fulfilled.match(result)) {
        const newSessionId = result.payload.session_id;
        const sendResult = await dispatch(sendMessage({
          sessionId: newSessionId,
          content,
          isFirstMessage: true,
          messageId,
          timestamp,
        }));
        
        // Fetch and update session title after first message
        if (sendMessage.fulfilled.match(sendResult)) {
          try {
            const titleData = await apiService.getSessionTitle(newSessionId);
            dispatch(updateSessionTitle({ sessionId: newSessionId, title: titleData.title }));
          } catch (error) {
            console.error('Failed to fetch session title:', error);
          }
        }
      }
    } else {
      const isFirstMessage = messages.length === 0;
      const sendResult = await dispatch(sendMessage({
        sessionId: currentSessionId,
        content,
        isFirstMessage,
        messageId,
        timestamp,
      }));
      
      // Fetch and update session title after first message
      if (isFirstMessage && sendMessage.fulfilled.match(sendResult)) {
        try {
          const titleData = await apiService.getSessionTitle(currentSessionId);
          dispatch(updateSessionTitle({ sessionId: currentSessionId, title: titleData.title }));
        } catch (error) {
          console.error('Failed to fetch session title:', error);
        }
      }
    }
  };

  const handleExampleClick = (example: string) => {
    handleSendMessage(example);
  };

  return (
    <div className="h-screen flex overflow-hidden bg-gray-50">
      {/* Sidebar */}
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-3">
          <button
            onClick={() => setSidebarOpen(true)}
            className="lg:hidden p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <Menu size={24} />
          </button>
          <h1 className="text-lg font-semibold text-gray-900">
            {currentSessionId ? 'Chat Session' : 'Viva'}
          </h1>
        </header>

        {/* Error Banner */}
        {error && (
          <div className="bg-red-50 border-b border-red-200 px-4 py-3 flex items-center gap-3">
            <AlertCircle className="text-red-600 flex-shrink-0" size={20} />
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {/* Messages Container */}
        <div className="flex-1 overflow-y-auto">
          {messages.length === 0 ? (
            <EmptyState onExampleClick={handleExampleClick} />
          ) : (
            <div>
              {messages.map((message) => (
                <ChatMessage key={message.message_id} message={message} />
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Chat Input */}
        <ChatInput
          onSend={handleSendMessage}
          disabled={sending}
          placeholder={
            sending
              ? 'Assistant is typing...'
              : currentSessionId || messages.length > 0
              ? 'Type your message...'
              : 'Start a new conversation...'
          }
        />
      </div>
    </div>
  );
};
