import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { User, Bot, Copy, Check } from 'lucide-react';
import type { Message } from '@/types';
import { formatMessageTime } from '@/utils/formatDate';

interface ChatMessageProps {
  message: Message;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const [copied, setCopied] = React.useState(false);
  const isUser = message.role === 'user';

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="px-4 py-6">
      <div
        className={`
          flex gap-3 max-w-4xl mx-auto
          ${isUser ? 'justify-start' : 'justify-end'}
        `}
      >
        {/* User message - left side */}
        {isUser && (
          <>
            {/* Avatar */}
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center">
              <User size={20} className="text-white" />
            </div>

            {/* Content */}
            <div className="flex-1 max-w-[70%]">
              <div className="flex items-center gap-2 mb-1">
                <span className="font-semibold text-sm">You</span>
                <span className="text-xs text-gray-500">
                  {formatMessageTime(message.timestamp)}
                </span>
              </div>
              <div className="bg-blue-100 rounded-2xl rounded-tl-none px-4 py-3 text-gray-800 whitespace-pre-wrap break-words">
                {message.content}
              </div>
            </div>
          </>
        )}

        {/* Agent message - right side */}
        {!isUser && (
          <>
            {/* Content */}
            <div className="flex-1 max-w-[70%]">
              <div className="flex items-center gap-2 mb-1 justify-end">
                <span className="text-xs text-gray-500">
                  {formatMessageTime(message.timestamp)}
                </span>
                <span className="font-semibold text-sm">Assistant</span>
              </div>
              <div className="bg-green-50 rounded-2xl rounded-tr-none px-4 py-3 border border-green-200">
                <div className="prose prose-sm max-w-none prose-headings:text-gray-900 prose-p:text-gray-800 prose-strong:text-gray-900 prose-code:text-gray-900">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={{
                      code({ node, inline, className, children, ...props }) {
                        const match = /language-(\w+)/.exec(className || '');
                        const codeString = String(children).replace(/\n$/, '');

                        return !inline && match ? (
                          <div className="relative group my-2">
                            <button
                              onClick={() => handleCopy(codeString)}
                              className="absolute right-2 top-2 p-2 rounded bg-gray-700 hover:bg-gray-600 text-white opacity-0 group-hover:opacity-100 transition-opacity z-10"
                              title="Copy code"
                            >
                              {copied ? <Check size={16} /> : <Copy size={16} />}
                            </button>
                            <SyntaxHighlighter
                              style={oneDark}
                              language={match[1]}
                              PreTag="div"
                              {...props}
                            >
                              {codeString}
                            </SyntaxHighlighter>
                          </div>
                        ) : (
                          <code className={`${className} bg-green-200 px-1 py-0.5 rounded text-sm`} {...props}>
                            {children}
                          </code>
                        );
                      },
                    }}
                  >
                    {message.content}
                  </ReactMarkdown>
                </div>
              </div>
            </div>

            {/* Avatar */}
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-green-600 flex items-center justify-center">
              <Bot size={20} className="text-white" />
            </div>
          </>
        )}
      </div>
    </div>
  );
};
