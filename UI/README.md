# Viva Chatbot - Frontend

A modern, ChatGPT-style UI built with React, TypeScript, Redux Toolkit, and Tailwind CSS.

## Features

- 🔐 **Authentication**: Secure login and registration
- 💬 **Real-time Chat**: Interactive chat interface with RAG-powered AI assistant
- 📝 **Session Management**: Create, view, and delete chat sessions
- 🎨 **Modern UI**: Beautiful, responsive design inspired by ChatGPT and Gemini
- ⚡ **State Management**: Redux Toolkit with TypeScript for type-safe state management
- 🎯 **Markdown Support**: Rich text formatting in messages with code highlighting
- 📱 **Responsive Design**: Works seamlessly on desktop, tablet, and mobile devices

## Tech Stack

- **React 18** - Modern React with hooks
- **TypeScript** - Type-safe development
- **Redux Toolkit** - State management
- **React Router** - Navigation
- **Tailwind CSS** - Utility-first styling
- **Vite** - Fast build tool
- **Axios** - HTTP client
- **React Markdown** - Markdown rendering
- **Lucide React** - Beautiful icons

## Prerequisites

- Node.js 18+ and npm
- Backend services running:
  - User Service (port 8001)
  - RAG Service (port 8005)

## Getting Started

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Configure Environment

The `.env` file is already configured with default values:

```env
VITE_USER_SERVICE_URL=http://localhost:8001
VITE_RAG_SERVICE_URL=http://localhost:8005
```

Update these if your backend services run on different ports.

### 3. Start Development Server

```bash
npm run dev
```

The application will open at `http://localhost:3000`

### 4. Build for Production

```bash
npm run build
```

The optimized production build will be in the `dist` folder.

### 5. Preview Production Build

```bash
npm run preview
```

## Project Structure

```
frontend/
├── src/
│   ├── components/        # Reusable UI components
│   │   ├── ChatInput.tsx
│   │   ├── ChatMessage.tsx
│   │   ├── EmptyState.tsx
│   │   └── Sidebar.tsx
│   ├── pages/             # Page components
│   │   ├── Chat.tsx
│   │   ├── Login.tsx
│   │   └── Register.tsx
│   ├── store/             # Redux store and slices
│   │   ├── authSlice.ts
│   │   ├── chatSlice.ts
│   │   └── index.ts
│   ├── services/          # API services
│   │   └── api.ts
│   ├── types/             # TypeScript types
│   │   └── index.ts
│   ├── utils/             # Utility functions
│   │   └── formatDate.ts
│   ├── hooks/             # Custom hooks
│   │   ├── useAppDispatch.ts
│   │   └── useAppSelector.ts
│   ├── App.tsx            # Main app component
│   ├── main.tsx           # Entry point
│   └── index.css          # Global styles
├── public/                # Static assets
├── index.html             # HTML template
├── package.json           # Dependencies
├── tsconfig.json          # TypeScript config
├── vite.config.ts         # Vite config
├── tailwind.config.js     # Tailwind config
└── README.md              # This file
```

## Key Features Explained

### Authentication Flow

1. User registers with email, username, and password
2. User logs in with email/username and password
3. JWT tokens are stored in localStorage
4. Protected routes redirect to login if not authenticated

### Chat Flow

1. User creates a new session or selects existing one
2. Messages are sent to RAG service via `/rag/{session_id}/chat` endpoint
3. Assistant responses are displayed in real-time
4. Messages are stored in the backend (Chat Service via RAG Service)
5. Session titles are auto-generated on first message

### State Management

- **Auth Slice**: Handles authentication, login, registration, and user state
- **Chat Slice**: Manages sessions, messages, and chat interactions

### API Integration

The app integrates with two backend services:

1. **User Service** (port 8001):
   - `/user/register` - Register new user
   - `/user/login` - Login user
   - `/user/get-sessions` - Get user sessions
   - `/user/{session_id}/get-session-title` - Get session title

2. **RAG Service** (port 8005):
   - `/rag/create-session` - Create new session
   - `/rag/get-sessions` - Get all sessions
   - `/rag/{session_id}/chat` - Send message and get response
   - `/rag/{session_id}/get-session-messages` - Get session messages
   - `/rag/{session_id}/delete-session` - Delete session

