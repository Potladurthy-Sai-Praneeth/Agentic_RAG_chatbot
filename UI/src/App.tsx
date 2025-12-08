import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Login } from '@/pages/Login';
import { Register } from '@/pages/Register';
import { Chat } from '@/pages/Chat';
import { useAppSelector } from '@/hooks/useAppSelector';
import { useAppDispatch } from '@/hooks/useAppDispatch';
import { validateToken, setNotAuthenticated, setupAuthInterceptor } from '@/store/authSlice';
import { setSessions, clearChatState } from '@/store/chatSlice';
import { Loader2 } from 'lucide-react';

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, loading } = useAppSelector((state) => state.auth);
  
  // Still validating token - show nothing
  if (loading) {
    return null;
  }
  
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />;
};

// Loading screen during initial validation
const LoadingScreen: React.FC = () => (
  <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
    <div className="text-center">
      <Loader2 size={48} className="animate-spin text-blue-600 mx-auto mb-4" />
      <p className="text-gray-600">Loading...</p>
    </div>
  </div>
);

function App() {
  const dispatch = useAppDispatch();
  const { loading } = useAppSelector((state) => state.auth);
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    // Setup the interceptor to handle 401 errors and clear chat state
    setupAuthInterceptor(dispatch, () => {
      dispatch(clearChatState());
    });
  }, [dispatch]);

  useEffect(() => {
    // Skip if already initialized
    if (initialized) return;
    
    // Check if we have a token to validate
    const token = localStorage.getItem('accessToken');
    
    if (token) {
      // Validate the existing token
      dispatch(validateToken())
        .unwrap()
        .then((result) => {
          // Store the sessions we got from validation
          if (result.sessions) {
            dispatch(setSessions(result.sessions));
          }
        })
        .catch(() => {
          // Token invalid - already handled by the thunk
        })
        .finally(() => {
          setInitialized(true);
        });
    } else {
      // No token - user is not authenticated
      dispatch(setNotAuthenticated());
      setInitialized(true);
    }
  }, [dispatch, initialized]);

  // Show loading screen during initial token validation
  if (!initialized || loading) {
    return <LoadingScreen />;
  }

  return (
    <Router>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route
          path="/chat"
          element={
            <ProtectedRoute>
              <Chat />
            </ProtectedRoute>
          }
        />
        <Route path="/" element={<Navigate to="/chat" replace />} />
      </Routes>
    </Router>
  );
}

export default App;
