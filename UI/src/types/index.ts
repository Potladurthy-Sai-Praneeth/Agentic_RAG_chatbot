// Auth Types
export interface User {
  userId: string;
  email: string;
  username: string;
}

export interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  loading: boolean;
  error: string | null;
}

export interface LoginCredentials {
  user: string;
  password: string;
}

export interface RegisterCredentials {
  email: string;
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

// Chat Types
export interface Message {
  message_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
}

export interface Session {
  session_id: string;
  created_at: string;
  title?: string;
}

export interface ChatState {
  sessions: Session[];
  currentSessionId: string | null;
  messages: Message[];
  loading: boolean;
  sending: boolean;
  error: string | null;
}

// API Request/Response Types
export interface ChatRequest {
  message_id: string;
  role: 'user';
  content: string;
  timestamp: string;
  is_first_message: boolean;
}

export interface ChatResponse {
  message_id: string;
  timestamp: string;
  success: boolean;
  response: string;
}

export interface CreateSessionResponse {
  session_id: string;
  created_at: string;
}

export interface GetSessionsResponse {
  success: boolean;
  sessions: Session[];
}

export interface DeleteSessionResponse {
  success: boolean;
  message: string;
}
