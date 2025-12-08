import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import type { AxiosError } from 'axios';
import { apiService } from '@/services/api';
import type { ChatState, Message, Session, ChatRequest } from '@/types';

// Simple UUID generator
const generateUUID = () => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
};

const initialState: ChatState = {
  sessions: [],
  currentSessionId: null,
  messages: [],
  loading: false,
  sending: false,
  error: null,
};

const getErrorMessage = (error: unknown, fallback: string) => {
  const axiosError = error as AxiosError<{ detail?: string }>;
  return axiosError?.response?.data?.detail || axiosError?.message || fallback;
};

// Async thunks
export const fetchSessions = createAsyncThunk(
  'chat/fetchSessions',
  async (_, { rejectWithValue }) => {
    try {
      const sessions = await apiService.getSessions();
      return sessions;
    } catch (error: any) {
      return rejectWithValue(getErrorMessage(error, 'Failed to fetch sessions'));
    }
  }
);

export const createNewSession = createAsyncThunk(
  'chat/createNewSession',
  async (_, { rejectWithValue }) => {
    try {
      const session = await apiService.createSession();
      return session;
    } catch (error: any) {
      return rejectWithValue(getErrorMessage(error, 'Failed to create session'));
    }
  }
);

export const deleteSession = createAsyncThunk(
  'chat/deleteSession',
  async (sessionId: string, { rejectWithValue }) => {
    try {
      await apiService.deleteSession(sessionId);
      return sessionId;
    } catch (error: any) {
      return rejectWithValue(getErrorMessage(error, 'Failed to delete session'));
    }
  }
);

export const fetchSessionMessages = createAsyncThunk(
  'chat/fetchSessionMessages',
  async (sessionId: string, { rejectWithValue }) => {
    try {
      const messages = await apiService.getSessionMessages(sessionId);
      return messages;
    } catch (error: any) {
      return rejectWithValue(getErrorMessage(error, 'Failed to fetch messages'));
    }
  }
);

export const sendMessage = createAsyncThunk(
  'chat/sendMessage',
  async ({ 
    sessionId, 
    content, 
    isFirstMessage, 
    messageId, 
    timestamp 
  }: { 
    sessionId: string; 
    content: string; 
    isFirstMessage: boolean;
    messageId: string;
    timestamp: string;
  }, { rejectWithValue }) => {
    try {
      const request: ChatRequest = {
        message_id: messageId,
        role: 'user',
        content,
        timestamp,
        is_first_message: isFirstMessage,
      };

      const response = await apiService.sendMessage(sessionId, request);
      
      return {
        userMessage: {
          message_id: messageId,
          role: 'user' as const,
          content,
          timestamp,
        },
        assistantMessage: {
          message_id: response.message_id,
          role: 'assistant' as const,
          content: response.response,
          timestamp: response.timestamp,
        },
      };
    } catch (error: any) {
      return rejectWithValue(getErrorMessage(error, 'Failed to send message'));
    }
  }
);

const chatSlice = createSlice({
  name: 'chat',
  initialState,
  reducers: {
    setCurrentSession: (state, action: PayloadAction<string>) => {
      state.currentSessionId = action.payload;
      state.messages = [];
    },
    setSessions: (state, action: PayloadAction<Session[]>) => {
      state.sessions = action.payload;
    },
    clearMessages: (state) => {
      state.messages = [];
    },
    clearError: (state) => {
      state.error = null;
    },
    clearChatState: (state) => {
      state.sessions = [];
      state.currentSessionId = null;
      state.messages = [];
      state.loading = false;
      state.sending = false;
      state.error = null;
    },
    addOptimisticMessage: (state, action: PayloadAction<Message>) => {
      state.messages.push(action.payload);
    },
    updateSessionTitle: (state, action: PayloadAction<{ sessionId: string; title: string }>) => {
      const session = state.sessions.find(s => s.session_id === action.payload.sessionId);
      if (session) {
        session.title = action.payload.title;
      }
    },
  },
  extraReducers: (builder) => {
    builder
      // Fetch Sessions
      .addCase(fetchSessions.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchSessions.fulfilled, (state, action: PayloadAction<Session[]>) => {
        state.loading = false;
        state.sessions = action.payload;
      })
      .addCase(fetchSessions.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      })
      // Create Session
      .addCase(createNewSession.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(createNewSession.fulfilled, (state, action) => {
        state.loading = false;
        state.sessions.unshift(action.payload);
        state.currentSessionId = action.payload.session_id;
        state.messages = [];
      })
      .addCase(createNewSession.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      })
      // Delete Session
      .addCase(deleteSession.fulfilled, (state, action: PayloadAction<string>) => {
        state.sessions = state.sessions.filter(s => s.session_id !== action.payload);
        if (state.currentSessionId === action.payload) {
          state.currentSessionId = null;
          state.messages = [];
        }
      })
      // Fetch Messages
      .addCase(fetchSessionMessages.pending, (state) => {
        state.loading = true;
        state.error = null;
        // Clear messages to prevent mixing between sessions
        state.messages = [];
      })
      .addCase(fetchSessionMessages.fulfilled, (state, action: PayloadAction<Message[]>) => {
        state.loading = false;
        state.messages = action.payload;
      })
      .addCase(fetchSessionMessages.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      })
      // Send Message
      .addCase(sendMessage.pending, (state, action) => {
        state.sending = true;
        state.error = null;
        // Add user message immediately (optimistic update)
        const { messageId, content, timestamp } = action.meta.arg;
        state.messages.push({
          message_id: messageId,
          role: 'user',
          content,
          timestamp,
        });
      })
      .addCase(sendMessage.fulfilled, (state, action) => {
        state.sending = false;
        // Only add the assistant message (user message already added in pending)
        state.messages.push(action.payload.assistantMessage);
      })
      .addCase(sendMessage.rejected, (state, action) => {
        state.sending = false;
        state.error = action.payload as string;
        // Remove the optimistically added user message on error
        state.messages.pop();
      });
  },
});

export const { setCurrentSession, setSessions, clearMessages, clearError, clearChatState, addOptimisticMessage, updateSessionTitle } = chatSlice.actions;
export default chatSlice.reducer;
