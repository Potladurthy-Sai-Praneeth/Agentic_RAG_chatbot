import React, { useEffect, useRef } from 'react';
import { useAppDispatch } from '@/hooks/useAppDispatch';
import { useAppSelector } from '@/hooks/useAppSelector';
import {
  fetchSessions,
  createNewSession,
  deleteSession,
  setCurrentSession,
  fetchSessionMessages,
  clearChatState,
} from '@/store/chatSlice';
import { logoutAndClearCache } from '@/store/authSlice';
import { PlusCircle, MessageSquare, Trash2, LogOut, X } from 'lucide-react';
import { formatRelativeTime } from '@/utils/formatDate';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const dispatch = useAppDispatch();
  const { sessions, currentSessionId, loading } = useAppSelector((state) => state.chat);
  const { isAuthenticated } = useAppSelector((state) => state.auth);
  const hasFetchedRef = useRef(false);

  useEffect(() => {
    // Only fetch if authenticated, not already fetched, and no sessions loaded yet
    // Sessions might already be loaded from validateToken
    if (isAuthenticated && !hasFetchedRef.current && sessions.length === 0) {
      hasFetchedRef.current = true;
      dispatch(fetchSessions());
    }
    
    // Reset the ref when logged out
    if (!isAuthenticated) {
      hasFetchedRef.current = false;
    }
  }, [dispatch, isAuthenticated, sessions.length]);

  const handleCreateSession = async () => {
    const result = await dispatch(createNewSession());
    if (createNewSession.fulfilled.match(result)) {
      // Close sidebar on mobile after creating session
      if (window.innerWidth < 1024) {
        onClose();
      }
    }
  };

  const handleSelectSession = async (sessionId: string) => {
    // Clear current messages and set new session
    dispatch(setCurrentSession(sessionId));
    // Fetch messages for the new session
    await dispatch(fetchSessionMessages(sessionId));
    // Close sidebar on mobile
    onClose();
  };

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (window.confirm('Are you sure you want to delete this session?')) {
      await dispatch(deleteSession(sessionId));
    }
  };

  const handleLogout = async () => {
    // Clear chat state first
    dispatch(clearChatState());
    // Logout and clear all cached sessions in Redis
    await dispatch(logoutAndClearCache());
    onClose();
  };

  return (
    <>
      {/* Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black bg-opacity-50 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed lg:static inset-y-0 left-0 z-50
          w-80 bg-gray-900 text-white
          transform transition-transform duration-300 ease-in-out
          ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          flex flex-col
        `}
      >
        {/* Header */}
        <div className="p-4 border-b border-gray-800 flex items-center justify-between">
          <h2 className="text-xl font-bold">Viva</h2>
          <button
            onClick={onClose}
            className="lg:hidden text-gray-400 hover:text-white"
          >
            <X size={24} />
          </button>
        </div>

        {/* New Chat Button */}
        <div className="p-4">
          <button
            onClick={handleCreateSession}
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed rounded-lg transition-colors font-medium"
          >
            <PlusCircle size={20} />
            New Chat
          </button>
        </div>

        {/* Sessions List */}
        <div className="flex-1 overflow-y-auto px-2">
          {loading && sessions.length === 0 ? (
            <div className="text-center text-gray-500 py-8">Loading sessions...</div>
          ) : sessions.length === 0 ? (
            <div className="text-center text-gray-500 py-8">
              No sessions yet. Create a new chat to get started!
            </div>
          ) : (
            <div className="space-y-2">
              {sessions.map((session) => (
                <div
                  key={session.session_id}
                  onClick={() => handleSelectSession(session.session_id)}
                  className={`
                    group relative flex items-center gap-3 px-3 py-3 rounded-lg cursor-pointer
                    transition-colors
                    ${
                      currentSessionId === session.session_id
                        ? 'bg-gray-800'
                        : 'hover:bg-gray-800/50'
                    }
                  `}
                >
                  <MessageSquare size={18} className="flex-shrink-0 text-gray-400" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm truncate">
                      {session.title || 'New Conversation'}
                    </p>
                    <p className="text-xs text-gray-500">
                      {formatRelativeTime(session.created_at)}
                    </p>
                  </div>
                  <button
                    onClick={(e) => handleDeleteSession(session.session_id, e)}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-600 rounded transition-opacity"
                    title="Delete session"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-gray-800">
          <button
            onClick={handleLogout}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 text-gray-300 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
          >
            <LogOut size={20} />
            Logout
          </button>
        </div>
      </aside>
    </>
  );
};
