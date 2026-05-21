import React, { useState } from 'react';

export interface DiagramItem {
  id: string;
  prompt: string;
  audience?: string;
  aspect_ratio: string;
  resolution: string;
  imageUrl: string;
  created_at: string;
}

interface CanvasPanelProps {
  activeDiagram: DiagramItem | null;
  history: DiagramItem[];
  config: {
    aspect_ratio: string;
    resolution: string;
    audience: string;
    codebase_path: string;
    use_codebase: boolean;
  };
  onChangeConfig: (key: string, value: any) => void;
  onSelectDiagram: (item: DiagramItem) => void;
}

export const CanvasPanel: React.FC<CanvasPanelProps> = ({
  activeDiagram,
  history,
  config,
  onChangeConfig,
  onSelectDiagram,
}) => {
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const handleDownload = () => {
    if (!activeDiagram) return;
    const link = document.createElement('a');
    link.href = activeDiagram.imageUrl;
    link.download = `etch_diagram_${activeDiagram.id.slice(0, 8)}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleCopy = async () => {
    if (!activeDiagram) return;
    try {
      const response = await fetch(activeDiagram.imageUrl);
      const blob = await response.blob();
      await navigator.clipboard.write([
        new ClipboardItem({ [blob.type]: blob })
      ]);
      alert("Image copied to clipboard successfully!");
    } catch (err) {
      alert("Failed to copy image: " + err);
    }
  };

  return (
    <div className="panel" style={{ borderRight: 'none' }}>
      <div className="panel-header">
        <h2>🎨 Canvas & History</h2>
        <button className="settings-btn" onClick={() => setIsDrawerOpen(true)}>
          ⚙️ Configurations
        </button>
      </div>

      {/* Dynamic Slide-out Drawer */}
      <div className={`drawer-overlay ${isDrawerOpen ? 'open' : ''}`}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
          <h3 style={{ margin: 0, fontFamily: 'var(--font-outfit)', color: 'var(--accent-teal)' }}>⚙️ Drawing Settings</h3>
          <button className="settings-btn" onClick={() => setIsDrawerOpen(false)}>Close</button>
        </div>

        <div className="settings-group">
          <label>Aspect Ratio</label>
          <select
            className="settings-select"
            value={config.aspect_ratio}
            onChange={(e) => onChangeConfig('aspect_ratio', e.target.value)}
          >
            <option value="16:9">16:9 (Widescreen)</option>
            <option value="1:1">1:1 (Square)</option>
            <option value="9:16">9:16 (Vertical)</option>
            <option value="4:3">4:3 (Classic)</option>
            <option value="3:4">3:4 (Portrait)</option>
            <option value="21:9">21:9 (Ultrawide)</option>
          </select>
        </div>

        <div className="settings-group">
          <label>Resolution</label>
          <select
            className="settings-select"
            value={config.resolution}
            onChange={(e) => onChangeConfig('resolution', e.target.value)}
          >
            <option value="1K">1K Standard</option>
            <option value="2K">2K High-Definition</option>
          </select>
        </div>

        <div className="settings-group">
          <label>Target Audience (Prose)</label>
          <input
            type="text"
            className="settings-input"
            value={config.audience}
            onChange={(e) => onChangeConfig('audience', e.target.value)}
            placeholder="e.g., onboarding engineer"
          />
        </div>

        <div className="settings-group" style={{ display: 'flex', flexDirection: 'row', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
          <input
            type="checkbox"
            id="use-codebase-chk"
            checked={config.use_codebase}
            onChange={(e) => onChangeConfig('use_codebase', e.target.checked)}
            style={{ width: '18px', height: '18px', cursor: 'pointer', accentColor: 'var(--accent-teal)' }}
          />
          <label htmlFor="use-codebase-chk" style={{ cursor: 'pointer', margin: 0, userSelect: 'none', color: 'var(--text-primary)' }}>
            Include local codebase context (file tree)
          </label>
        </div>

        <div className="settings-group" style={{ opacity: config.use_codebase ? 1 : 0.4, transition: 'opacity 0.2s' }}>
          <label>Active Codebase Absolute Path</label>
          <input
            type="text"
            className="settings-input"
            value={config.codebase_path}
            onChange={(e) => onChangeConfig('codebase_path', e.target.value)}
            placeholder="/Users/username/project"
            disabled={!config.use_codebase}
          />
        </div>
      </div>

      {/* Main interactive canvas viewer */}
      <div className="canvas-view">
        {activeDiagram ? (
          <div className="canvas-inner">
            <img src={activeDiagram.imageUrl} alt={activeDiagram.prompt} />
            <div className="canvas-overlay-btn">
              <button className="action-btn" title="Download Image" onClick={handleDownload}>📥</button>
              <button className="action-btn" title="Copy Clipboard" onClick={handleCopy}>📋</button>
            </div>
            <div style={{ position: 'absolute', bottom: '12px', left: '12px', background: 'rgba(0,0,0,0.7)', padding: '6px 12px', borderRadius: '4px', fontSize: '0.75rem', border: '1px solid var(--border-color)', color: 'var(--text-secondary)' }}>
              <strong>Prompt:</strong> {activeDiagram.prompt.slice(0, 50)}... | <strong>Ratio:</strong> {activeDiagram.aspect_ratio}
            </div>
          </div>
        ) : (
          <div style={{ color: 'var(--text-muted)', textAlign: 'center', fontSize: '0.9rem' }}>
            No active diagram loaded. Sketch one in the chat.
          </div>
        )}
      </div>

      {/* Gallery bottom sliding tray */}
      <div className="gallery-pane">
        <div className="gallery-title">📁 Recent Sketches ({history.length})</div>
        <div className="gallery-items">
          {history.map((item) => (
            <div
              key={item.id}
              className={`gallery-item ${activeDiagram?.id === item.id ? 'active' : ''}`}
              onClick={() => onSelectDiagram(item)}
            >
              <img src={item.imageUrl} alt={item.prompt} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
