import React from 'react';
import { MessageSquarePlus, Sparkles, FileQuestion, Lightbulb } from 'lucide-react';

interface EmptyStateProps {
  onExampleClick?: (example: string) => void;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ onExampleClick }) => {
  const examples = [
    {
      icon: <FileQuestion size={20} />,
      text: 'Explain quantum computing in simple terms',
    },
    {
      icon: <Lightbulb size={20} />,
      text: 'Help me write a professional email',
    },
    {
      icon: <Sparkles size={20} />,
      text: 'Create a Python function to sort a list',
    },
  ];

  return (
    <div className="flex-1 flex items-center justify-center p-8">
      <div className="max-w-3xl text-center">
        <div className="mb-8">
          <div className="inline-flex items-center justify-center w-20 h-20 bg-gradient-to-br from-blue-500 to-blue-600 rounded-full mb-4">
            <MessageSquarePlus size={40} className="text-white" />
          </div>
          <h1 className="text-4xl font-bold text-gray-900 mb-3">
            Welcome to Viva
          </h1>
          <p className="text-xl text-gray-600">
            Start a conversation or try one of these examples
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-4">
          {examples.map((example, index) => (
            <button
              key={index}
              onClick={() => onExampleClick?.(example.text)}
              className="p-4 bg-white border border-gray-200 rounded-lg hover:border-blue-500 hover:shadow-md transition-all text-left group"
            >
              <div className="flex items-start gap-3">
                <div className="flex-shrink-0 text-blue-600 group-hover:scale-110 transition-transform">
                  {example.icon}
                </div>
                <p className="text-sm text-gray-700 group-hover:text-gray-900">
                  {example.text}
                </p>
              </div>
            </button>
          ))}
        </div>

        <div className="mt-8 text-sm text-gray-500">
          <p>Powered by advanced RAG technology</p>
        </div>
      </div>
    </div>
  );
};
