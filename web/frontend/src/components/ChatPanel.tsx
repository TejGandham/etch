import React, { useRef, useEffect, useState } from 'react';

export interface Message {
  id: string;
  sender: 'user' | 'assistant';
  text: string;
  timestamp: Date;
  jobId?: string;
  status?: 'queued' | 'generating' | 'complete' | 'failed';
  imageUrl?: string;
  error?: string;
}

interface ChatPanelProps {
  messages: Message[];
  isGenerating: boolean;
  onSendPrompt: (prompt: string) => void;
}

export const ChatPanel: React.FC<ChatPanelProps> = ({ messages, isGenerating, onSendPrompt }) => {
  const [inputValue, setInputValue] = useState('');
  const feedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isGenerating) return;
    onSendPrompt(inputValue.trim());
    setInputValue('');
  };

  const handleQuickPill = (text: string) => {
    setInputValue((prev) => (prev ? `${prev} ${text}` : text));
  };

  return (
    <div className="panel">
      <div className="panel-header">
        <h2>💬 etch drawing room</h2>
        {isGenerating && (
          <div className="pulse-indicator">
            <span className="pulse-dot"></span>
            <span>Sketching...</span>
          </div>
        )}
      </div>

      <div className="chat-feed" ref={feedRef}>
        {messages.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', textAlign: 'center', marginTop: '40px', fontSize: '0.9rem' }}>
            No diagrams etched yet. Prompt me on the code structure, microservices, database, or UI auth journeys to begin.
          </div>
        ) : (
          messages.map((msg) => (
            <div key={msg.id} className={`chat-message ${msg.sender}`}>
              {msg.sender === 'user' ? (
                <div>{msg.text}</div>
              ) : (
                <div>
                  {msg.status === 'queued' && (
                    <div className="pulse-indicator">
                      <span className="pulse-dot"></span>
                      <span>Job queued in Etch...</span>
                    </div>
                  )}
                  {msg.status === 'generating' && (
                    <div className="pulse-indicator">
                      <span className="pulse-dot"></span>
                      <span>Sketches in progress (approx. 30s)...</span>
                    </div>
                  )}
                  {msg.status === 'failed' && (
                    <div style={{ color: '#ef4444' }}>
                      ⚠️ Diagram generation failed: {msg.error || 'Unknown error'}
                    </div>
                  )}
                  {msg.status === 'complete' && (
                    <div>
                      <div>✨ Diagram etched successfully!</div>
                      {msg.imageUrl && (
                        <div style={{ marginTop: '10px', borderRadius: '8px', overflow: 'hidden', border: '1px solid var(--border-color)' }}>
                          <img src={msg.imageUrl} alt="Etched thumbnail" style={{ width: '100%', height: 'auto', display: 'block' }} />
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))
        )}
      </div>

      <form className="chat-input-area" onSubmit={handleSubmit}>
        <div className="quick-pills">
          <button type="button" className="pill-btn" onClick={() => handleQuickPill("for Developers")}>+ for Developers</button>
          <button type="button" className="pill-btn" onClick={() => handleQuickPill("for Product Managers")}>+ for PMs</button>
          <button type="button" className="pill-btn" onClick={() => handleQuickPill("for Onboarding")}>+ for Onboarding</button>
          <button type="button" className="pill-btn" onClick={() => handleQuickPill("no-jargon onboarding journey")}>+ simple journey</button>
        </div>
        <div className="input-wrapper">
          <input
            type="text"
            className="text-input"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder={isGenerating ? "Drawing in progress..." : "Explain what to sketch..."}
            disabled={isGenerating}
          />
          <button type="submit" className="send-btn" disabled={isGenerating || !inputValue.trim()}>
            Draw
          </button>
        </div>
      </form>
    </div>
  );
};
