import React, { useState, useEffect } from 'react';
import { ChatPanel, Message } from './components/ChatPanel';
import { CanvasPanel, DiagramItem } from './components/CanvasPanel';

const App: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [history, setHistory] = useState<DiagramItem[]>([]);
  const [activeDiagram, setActiveDiagram] = useState<DiagramItem | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  
  // Configurations state
  const [config, setConfig] = useState({
    aspect_ratio: '16:9',
    resolution: '2K',
    audience: '',
    codebase_path: '', // Defaults to backend execution root
  });

  useEffect(() => {
    // Get health info to populate default workspace path
    fetch('/api/health')
      .then((res) => res.json())
      .then((data) => {
        if (data.workspace) {
          setConfig((prev) => ({ ...prev, codebase_path: data.workspace }));
        }
      })
      .catch(() => {});

    // Load initial diagram history
    refreshHistory();
  }, []);

  const refreshHistory = async () => {
    try {
      const response = await fetch('/api/history');
      const items = await response.json();
      setHistory(items);
      if (items.length > 0 && !activeDiagram) {
        setActiveDiagram(items[0]);
      }
    } catch (err) {
      console.error("Failed to load history:", err);
    }
  };

  const handleConfigChange = (key: string, value: string) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
  };

  const handleSendPrompt = async (prompt: string) => {
    setIsGenerating(true);

    const userMessageId = 'user-' + Date.now();
    const assistantMessageId = 'assistant-' + Date.now();

    const newMessages: Message[] = [
      ...messages,
      { id: userMessageId, sender: 'user', text: prompt, timestamp: new Date() },
      { id: assistantMessageId, sender: 'assistant', text: 'Queueing...', timestamp: new Date(), status: 'queued' }
    ];
    setMessages(newMessages);

    try {
      // 1. Submit drawing request
      const res = await fetch('/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          description: prompt,
          aspect_ratio: config.aspect_ratio,
          resolution: config.resolution,
          audience: config.audience || null,
          codebase_path: config.codebase_path || null
        })
      });

      if (!res.ok) {
        throw new Error(`Failed to submit job: ${res.statusText}`);
      }

      const data = await res.json();
      const jobId = data.job_id;

      // Update placeholder with jobId
      setMessages((prev) =>
        prev.map((m) => (m.id === assistantMessageId ? { ...m, jobId } : m))
      );

      // 2. Open Real-time SSE status connection
      const eventSource = new EventSource(`/api/jobs/stream/${jobId}`);

      eventSource.addEventListener('status', (e: any) => {
        const payload = JSON.parse(e.data);
        const status = payload.status;

        setMessages((prev) =>
          prev.map((m) => {
            if (m.id === assistantMessageId) {
              return {
                ...m,
                status: status,
                imageUrl: payload.imageUrl,
                error: payload.error
              };
            }
            return m;
          })
        );

        if (status === 'complete') {
          eventSource.close();
          setIsGenerating(false);
          
          // Build Diagram Item and add to gallery
          const newItem: DiagramItem = {
            id: jobId,
            prompt: prompt,
            audience: config.audience || undefined,
            aspect_ratio: config.aspect_ratio,
            resolution: config.resolution,
            imageUrl: payload.imageUrl,
            created_at: new Date().toISOString()
          };
          
          setHistory((prev) => [newItem, ...prev]);
          setActiveDiagram(newItem);
        } else if (status === 'failed') {
          eventSource.close();
          setIsGenerating(false);
        }
      });

      eventSource.onerror = () => {
        eventSource.close();
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMessageId
              ? { ...m, status: 'failed', error: 'Connection to stream broken.' }
              : m
          )
        );
        setIsGenerating(false);
      };

    } catch (err: any) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantMessageId
            ? { ...m, status: 'failed', error: err.message || 'Network error occurred.' }
            : m
        )
      );
      setIsGenerating(false);
    }
  };

  return (
    <div className="dashboard-container">
      <ChatPanel
        messages={messages}
        isGenerating={isGenerating}
        onSendPrompt={handleSendPrompt}
      />
      <CanvasPanel
        activeDiagram={activeDiagram}
        history={history}
        config={config}
        onChangeConfig={handleConfigChange}
        onSelectDiagram={setActiveDiagram}
      />
    </div>
  );
};

export default App;
