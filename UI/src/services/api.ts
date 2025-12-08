import axios, { AxiosInstance, AxiosError, InternalAxiosRequestConfig } from 'axios';
import type {
  LoginCredentials,
  RegisterCredentials,
  LoginResponse,
  ChatRequest,
  ChatResponse,
  Message,
  Session,
  CreateSessionResponse,
  DeleteSessionResponse,
} from '@/types';

// API Configuration
const USER_SERVICE_URL = import.meta.env.VITE_USER_SERVICE_URL || 'http://localhost:8001';
const RAG_SERVICE_URL = import.meta.env.VITE_RAG_SERVICE_URL || 'http://localhost:8005';
const REQUEST_TIMEOUT = Number(import.meta.env.VITE_API_TIMEOUT || 30000);
const TIMEOUT_MESSAGE = 'Request timed out. Please try again.';
const OFFLINE_MESSAGE = 'Unable to reach the service. Please check that it is running.';

// Callback to handle logout - will be set by the store
let onUnauthorized: (() => void) | null = null;

export const setUnauthorizedHandler = (handler: () => void) => {
  onUnauthorized = handler;
};

class ApiService {
  private userApi: AxiosInstance;
  private ragApi: AxiosInstance;

  constructor() {
    this.userApi = axios.create({
      baseURL: USER_SERVICE_URL,
      timeout: REQUEST_TIMEOUT,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.ragApi = axios.create({
      baseURL: RAG_SERVICE_URL,
      timeout: REQUEST_TIMEOUT,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Add auth interceptor for protected routes
    this.setupInterceptors();
  }

  private setupInterceptors() {
    const authInterceptor = (config: InternalAxiosRequestConfig) => {
      const token = localStorage.getItem('accessToken');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    };

    this.userApi.interceptors.request.use(authInterceptor);
    this.ragApi.interceptors.request.use(authInterceptor);

    // Response interceptor for error handling
    const errorInterceptor = (error: AxiosError) => {
      const status = error.response?.status;
      const requestUrl = error.config?.url || '';

      const isAuthEndpoint = requestUrl.includes('/user/login') || requestUrl.includes('/user/register');

      if (status === 401 && !isAuthEndpoint) {
        // Token expired or invalid - call the handler to properly logout via Redux
        if (onUnauthorized) {
          onUnauthorized();
        }
      }

      if (error.code === 'ECONNABORTED') {
        error.message = TIMEOUT_MESSAGE;
      } else if (!error.response) {
        error.message = OFFLINE_MESSAGE;
      }

      return Promise.reject(error);
    };

    this.userApi.interceptors.response.use(
      (response) => response,
      errorInterceptor
    );
    this.ragApi.interceptors.response.use(
      (response) => response,
      errorInterceptor
    );
  }

  // Auth Endpoints
  async login(credentials: LoginCredentials): Promise<LoginResponse> {
    const response = await this.userApi.post<LoginResponse>('/user/login', credentials);
    return response.data;
  }

  async register(credentials: RegisterCredentials): Promise<{ success: boolean; message: string }> {
    const response = await this.userApi.post('/user/register', credentials);
    return response.data;
  }

  // Session Endpoints
  async getSessions(): Promise<Session[]> {
    const response = await this.ragApi.get<Session[]>('/rag/get-sessions');
    return response.data;
  }

  async createSession(): Promise<CreateSessionResponse> {
    const response = await this.ragApi.post<CreateSessionResponse>('/rag/create-session');
    return response.data;
  }

  async deleteSession(sessionId: string): Promise<DeleteSessionResponse> {
    const response = await this.ragApi.delete<DeleteSessionResponse>(`/rag/${sessionId}/delete-session`);
    return response.data;
  }

  async getSessionTitle(sessionId: string): Promise<{ session_id: string; title: string }> {
    const response = await this.userApi.get(`/user/${sessionId}/get-session-title`);
    return response.data;
  }

  // Chat Endpoints
  async getSessionMessages(sessionId: string): Promise<Message[]> {
    const response = await this.ragApi.get<Message[]>(`/rag/${sessionId}/get-session-messages`);
    return response.data;
  }

  async sendMessage(sessionId: string, message: ChatRequest): Promise<ChatResponse> {
    const response = await this.ragApi.post<ChatResponse>(`/rag/${sessionId}/chat`, message);
    return response.data;
  }

  // Health Check
  async healthCheck(): Promise<boolean> {
    try {
      await Promise.all([
        this.userApi.get('/health'),
        this.ragApi.get('/health'),
      ]);
      return true;
    } catch {
      return false;
    }
  }
}

export const apiService = new ApiService();
