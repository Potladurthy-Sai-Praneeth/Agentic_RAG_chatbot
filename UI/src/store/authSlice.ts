import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import type { AxiosError } from 'axios';
import { apiService, setUnauthorizedHandler } from '@/services/api';
import type { AuthState, LoginCredentials, RegisterCredentials, LoginResponse } from '@/types';

// Initial state - don't assume authenticated just because token exists
// We need to validate it first
const initialState: AuthState = {
  user: null,
  accessToken: localStorage.getItem('accessToken'),
  refreshToken: localStorage.getItem('refreshToken'),
  isAuthenticated: false, // Start as false, will be set after validation
  loading: false,
  error: null,
};

const getErrorMessage = (error: unknown, fallback: string) => {
  const axiosError = error as AxiosError<{ detail?: string }>;
  return axiosError?.response?.data?.detail || axiosError?.message || fallback;
};

// Async thunks
export const login = createAsyncThunk(
  'auth/login',
  async (credentials: LoginCredentials, { rejectWithValue }) => {
    try {
      const response = await apiService.login(credentials);
      return response;
    } catch (error: any) {
      return rejectWithValue(getErrorMessage(error, 'Login failed'));
    }
  }
);

export const register = createAsyncThunk(
  'auth/register',
  async (credentials: RegisterCredentials, { rejectWithValue }) => {
    try {
      const response = await apiService.register(credentials);
      return response;
    } catch (error: any) {
      return rejectWithValue(getErrorMessage(error, 'Registration failed'));
    }
  }
);

// Validate existing token by making a test API call
export const validateToken = createAsyncThunk(
  'auth/validateToken',
  async (_, { rejectWithValue }) => {
    const token = localStorage.getItem('accessToken');
    if (!token) {
      return rejectWithValue('No token found');
    }
    
    try {
      // Use getSessions as a validation call - if token is valid, this will succeed
      // We also get the sessions data which we'll dispatch to chatSlice
      const sessions = await apiService.getSessions();
      return { valid: true, sessions };
    } catch (error: any) {
      // Token is invalid or expired
      localStorage.removeItem('accessToken');
      localStorage.removeItem('refreshToken');
      return rejectWithValue('Token validation failed');
    }
  }
);

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    logout: (state) => {
      state.user = null;
      state.accessToken = null;
      state.refreshToken = null;
      state.isAuthenticated = false;
      state.loading = false;
      state.error = null;
      localStorage.removeItem('accessToken');
      localStorage.removeItem('refreshToken');
    },
    clearError: (state) => {
      state.error = null;
    },
    // Called when no token exists - mark initialization complete
    setNotAuthenticated: (state) => {
      state.isAuthenticated = false;
      state.loading = false;
    },
  },
  extraReducers: (builder) => {
    builder
      // Login
      .addCase(login.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(login.fulfilled, (state, action: PayloadAction<LoginResponse>) => {
        state.loading = false;
        state.accessToken = action.payload.access_token;
        state.refreshToken = action.payload.refresh_token;
        state.isAuthenticated = true;
        localStorage.setItem('accessToken', action.payload.access_token);
        localStorage.setItem('refreshToken', action.payload.refresh_token);
      })
      .addCase(login.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      })
      // Register
      .addCase(register.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(register.fulfilled, (state) => {
        state.loading = false;
      })
      .addCase(register.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      })
      // Validate Token
      .addCase(validateToken.pending, (state) => {
        state.loading = true;
      })
      .addCase(validateToken.fulfilled, (state) => {
        state.loading = false;
        state.isAuthenticated = true;
      })
      .addCase(validateToken.rejected, (state) => {
        state.loading = false;
        state.isAuthenticated = false;
        state.accessToken = null;
        state.refreshToken = null;
      });
  },
});

export const { logout, clearError, setNotAuthenticated } = authSlice.actions;

// Setup the unauthorized handler to dispatch logout
// Also accepts an optional callback to clear other state (like chat)
export const setupAuthInterceptor = (dispatch: (action: any) => void, clearOtherState?: () => void) => {
  setUnauthorizedHandler(() => {
    dispatch(logout());
    if (clearOtherState) {
      clearOtherState();
    }
  });
};

export default authSlice.reducer;
