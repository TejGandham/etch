# Etch Chat UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a sleek, local web dashboard for Etch containing a real-time conversational chat panel to prompt diagram generation and an interactive canvas panel showing active diagrams, configurations, and history, supported by a local FastAPI backend that automatically parses local codebase structures for context.

**Architecture:** A local full-stack split-dashboard consisting of a FastAPI + Pydantic python server running in the background and a Vite + React + TypeScript frontend client in the browser, communicating via Server-Sent Events (SSE) for zero-polling real-time updates and standard REST.

**Tech Stack:** FastAPI, Pydantic, uvicorn, sse-starlette, React 18, TypeScript, Vite, Vanilla CSS.

---

## Technical Decompositions and File Structures

```
/web
  /backend
    main.py              # FastAPI server (codebase scanner, REST APIs, SSE stream, Etch reuse)
    requirements.txt     # Python backend dependencies
    tests/
      test_main.py       # API integration tests
  /frontend
    package.json         # NodeJS frontend dependencies
    vite.config.ts       # Vite config
    tsconfig.json        # TypeScript config
    index.html           # Main entrypage
    /src
      main.tsx           # React mounting
      App.tsx            # Main state coordinator & EventSource handler
      index.css          # Cyberpunk dark HSL glassmorphism design tokens
      /components
        ChatPanel.tsx    # Left panel: Messages, Input, SSE status LEDs
        CanvasPanel.tsx  # Right panel: Interactive image canvas, configurations, gallery
```

---

## Implementation Tasks

### Task 1: Backend Setup, Dependencies, and Basic Server

**Files:**
- Create: `web/backend/requirements.txt`
- Create: `web/backend/main.py`
- Create: `web/backend/tests/test_main.py`

- [ ] **Step 1: Write requirements file**
  Create `web/backend/requirements.txt`:
  ```text
  fastapi>=0.110.0
  uvicorn>=0.28.0
  sse-starlette>=2.0.0
  pydantic>=2.6.0
  pytest>=8.0.0
  httpx>=0.27.0
  ```

- [ ] **Step 2: Initialize basic FastAPI server**
  Create `web/backend/main.py` with basic setup, CORS, and health-check endpoint:
  ```python
  import os
  from fastapi import FastAPI
  from fastapi.middleware.cors import CORSMiddleware
  from pydantic import BaseModel

  app = FastAPI(title="Etch API")

  app.add_middleware(
      CORSMiddleware,
      allow_origins=["*"],
      allow_credentials=True,
      allow_methods=["*"],
      allow_headers=["*"],
  )

  class HealthResponse(BaseModel):
      status: str
      workspace: str

  @app.get("/api/health", response_model=HealthResponse)
  async def health():
      return HealthResponse(
          status="healthy",
          workspace=os.getcwd()
      )
  ```

- [ ] **Step 3: Write failing server test**
  Create `web/backend/tests/test_main.py`:
  ```python
  import pytest
  from fastapi.testclient import TestClient
  from web.backend.main import app

  client = TestClient(app)

  def test_health_check():
      response = client.get("/api/health")
      assert response.status_code == 200
      data = response.json()
      assert data["status"] == "healthy"
      assert "workspace" in data
  ```

- [ ] **Step 4: Run the backend tests**
  Run: `pytest web/backend/tests/test_main.py -v`
  Expected: PASS

- [ ] **Step 5: Commit changes**
  ```bash
  git add web/backend/requirements.txt web/backend/main.py web/backend/tests/test_main.py
  git commit -m "feat: setup basic fastapi backend server and test suite"
  ```

---

### Task 2: Codebase Context Indexer & Scan Endpoints

**Files:**
- Modify: `web/backend/main.py`
- Create: `web/backend/tests/test_scan.py`

- [ ] **Step 1: Write the Scan API spec in test**
  Create `web/backend/tests/test_scan.py` verifying file tree scan and parsing logic:
  ```python
  import os
  import pytest
  from fastapi.testclient import TestClient
  from web.backend.main import app

  client = TestClient(app)

  def test_scan_codebase():
      # Scan active server directory
      response = client.post("/api/config/scan", json={"path": os.getcwd()})
      assert response.status_code == 200
      data = response.json()
      assert "tree" in data
      assert "readme" in data
      assert "is_valid" in data
      assert data["is_valid"] is True
  ```

- [ ] **Step 2: Run tests to verify failure**
  Run: `pytest web/backend/tests/test_scan.py -v`
  Expected: FAIL with "POST /api/config/scan 404 Not Found"

- [ ] **Step 3: Implement Codebase Scan & Indexing Logic in FastAPI**
  Modify `web/backend/main.py` to add `ScanRequest`, `ScanResponse`, scan function, and endpoint:
  ```python
  from pathlib import Path
  from typing import Optional

  class ScanRequest(BaseModel):
      path: str

  class ScanResponse(BaseModel):
      is_valid: bool
      tree: str
      readme: Optional[str]
      error: Optional[str] = None

  def build_file_tree(dir_path: Path, max_depth: int = 3, current_depth: int = 1) -> str:
      if not dir_path.exists() or not dir_path.is_dir():
          return ""
      lines = []
      ignore_folders = {".git", "node_modules", "venv", "__pycache__", "dist", "build", ".gemini", "superpowers-temp"}
      
      try:
          for item in sorted(dir_path.iterdir()):
              if item.name in ignore_folders or item.name.startswith("."):
                  continue
              indent = "  " * (current_depth - 1)
              if item.is_dir():
                  lines.append(f"{indent}📁 {item.name}/")
                  if current_depth < max_depth:
                      subtree = build_file_tree(item, max_depth, current_depth + 1)
                      if subtree:
                          lines.append(subtree)
              else:
                  lines.append(f"{indent}📄 {item.name}")
      except Exception as e:
          lines.append(f"Error listing directory: {e}")
      return "\n".join(lines)

  @app.post("/api/config/scan", response_model=ScanResponse)
  async def scan_codebase(req: ScanRequest):
      folder = Path(req.path)
      if not folder.exists() or not folder.is_dir():
          return ScanResponse(is_valid=False, tree="", readme=None, error="Directory does not exist")
      
      tree_text = build_file_tree(folder)
      
      readme_text = None
      readme_path = folder / "README.md"
      if readme_path.exists() and readme_path.is_file():
          try:
              readme_text = readme_path.read_text(encoding="utf-8")[:3000] # Limit size
          except Exception:
              pass
              
      return ScanResponse(is_valid=True, tree=tree_text, readme=readme_text)
  ```

- [ ] **Step 4: Verify scan tests pass**
  Run: `pytest web/backend/tests/test_scan.py -v`
  Expected: PASS

- [ ] **Step 5: Commit changes**
  ```bash
  git add web/backend/main.py web/backend/tests/test_scan.py
  git commit -m "feat: implement codebase tree indexer and directory context scanner"
  ```

---

### Task 3: Async Job Generation, Image Storage & SSE Stream

**Files:**
- Modify: `web/backend/main.py`
- Create: `web/backend/tests/test_jobs.py`

- [ ] **Step 1: Write test for diagram execution and SSE stream**
  Create `web/backend/tests/test_jobs.py` with mock job execution tests:
  ```python
  import pytest
  from fastapi.testclient import TestClient
  from web.backend.main import app

  client = TestClient(app)

  def test_job_submission():
      response = client.post("/api/jobs", json={
          "description": "draw auth sequence",
          "aspect_ratio": "16:9",
          "resolution": "2K"
      })
      assert response.status_code == 200
      data = response.json()
      assert "job_id" in data
      
  def test_sse_stream_not_found():
      response = client.get("/api/jobs/stream/invalid_id")
      assert response.status_code == 404
  ```

- [ ] **Step 2: Run tests to verify failures**
  Run: `pytest web/backend/tests/test_jobs.py -v`
  Expected: FAIL with "404 Not Found"

- [ ] **Step 3: Integrate etch.py logic and implement SSE event streaming in FastAPI**
  Modify `web/backend/main.py` to import `etch` elements, handle async background execution, serve static diagram PNGs, and manage SSE job statuses:
  ```python
  import sys
  import asyncio
  import uuid
  from datetime import datetime
  from fastapi import BackgroundTasks, HTTPException
  from fastapi.staticfiles import StaticFiles
  from sse_starlette.sse import EventSourceResponse

  # Add parent directory to path to reuse etch.py
  sys.path.append(str(Path(__file__).parent.parent.parent.resolve()))
  import etch

  # Configure output directory
  OUTPUT_DIR = Path(__file__).parent / "output"
  OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
  app.mount("/static", StaticFiles(directory=str(OUTPUT_DIR)), name="static")

  # Local active jobs in-memory cache
  jobs_cache: dict[str, dict] = {}

  class DiagramRequest(BaseModel):
      description: str
      aspect_ratio: str = "16:9"
      resolution: str = "2K"
      audience: Optional[str] = None
      codebase_path: Optional[str] = None

  def execute_generation_task(job_id: str, req: DiagramRequest):
      # Re-use prompt building
      try:
          jobs_cache[job_id]["status"] = "generating"
          
          # Inject codebase context if supplied
          full_description = req.description
          if req.codebase_path:
              folder = Path(req.codebase_path)
              if folder.exists():
                  tree_text = build_file_tree(folder, max_depth=2)
                  full_description = (
                      f"[Local Codebase Structure]\n{tree_text}\n\n"
                      f"[User Description]\n{req.description}"
                  )
          
          # Execute etch start job synchronously inside this thread pool worker
          # Since etch uses threading, we'll run its API client directly
          api_key = os.environ.get("GOOGLE_API_KEY")
          if not api_key:
              raise ValueError("GOOGLE_API_KEY env variable not set")
              
          etch._run_generation(
              job_id=job_id,
              api_key=api_key,
              description=full_description,
              audience=req.audience,
              aspect_ratio=req.aspect_ratio,
              resolution=req.resolution,
              output_dir=OUTPUT_DIR
          )
          
          # Check output status
          if etch._jobs.get(job_id) and etch._jobs[job_id]["status"] == "complete":
              file_path = Path(etch._jobs[job_id]["file_path"])
              jobs_cache[job_id]["status"] = "complete"
              jobs_cache[job_id]["imageUrl"] = f"/static/{file_path.name}"
          else:
              err = etch._jobs.get(job_id, {}).get("error", "Unknown error")
              jobs_cache[job_id]["status"] = "failed"
              jobs_cache[job_id]["error"] = err
      except Exception as e:
          jobs_cache[job_id]["status"] = "failed"
          jobs_cache[job_id]["error"] = str(e)

  @app.post("/api/jobs")
  async def start_job(req: DiagramRequest, background_tasks: BackgroundTasks):
      job_id = str(uuid.uuid4())
      jobs_cache[job_id] = {
          "status": "queued",
          "created_at": datetime.now().isoformat(),
          "description": req.description,
          "aspect_ratio": req.aspect_ratio,
          "resolution": req.resolution,
          "audience": req.audience,
          "imageUrl": None,
          "error": None
      }
      
      background_tasks.add_task(execute_generation_task, job_id, req)
      return {"job_id": job_id}

  @app.get("/api/jobs/stream/{job_id}")
  async def stream_job_status(job_id: str):
      if job_id not in jobs_cache:
          raise HTTPException(status_code=404, detail="Job not found")
          
      async def event_generator():
          last_status = None
          while True:
              job = jobs_cache.get(job_id)
              if not job:
                  break
              current_status = job["status"]
              
              if current_status != last_status:
                  last_status = current_status
                  payload = {
                      "status": current_status,
                      "imageUrl": job.get("imageUrl"),
                      "error": job.get("error")
                  }
                  yield {"event": "status", "data": payload}
                  
              if current_status in ("complete", "failed"):
                  break
                  
              await asyncio.sleep(1)
              
      return EventSourceResponse(event_generator())

  @app.get("/api/history")
  async def get_history():
      history_items = []
      for jid, job in sorted(jobs_cache.items(), key=lambda x: x[1]["created_at"], reverse=True):
          if job["status"] == "complete":
              history_items.append({
                  "id": jid,
                  "prompt": job["description"],
                  "audience": job["audience"],
                  "aspect_ratio": job["aspect_ratio"],
                  "resolution": job["resolution"],
                  "imageUrl": job["imageUrl"],
                  "created_at": job["created_at"]
              })
      return history_items
  ```

- [ ] **Step 4: Run tests and verify health, scan, and job routes all pass**
  Run: `pytest web/backend/tests/ -v`
  Expected: PASS

- [ ] **Step 5: Commit changes**
  ```bash
  git add web/backend/main.py web/backend/tests/test_jobs.py
  git commit -m "feat: implement async background job execution, SSE status streamer, and static assets server"
  ```

---

### Task 4: Scaffolding Vite + React + TS Frontend

**Files:**
- Create: `web/frontend/package.json`
- Create: `web/frontend/vite.config.ts`
- Create: `web/frontend/tsconfig.json`
- Create: `web/frontend/index.html`
- Create: `web/frontend/src/main.tsx`

- [ ] **Step 1: Create package.json**
  Create `web/frontend/package.json`:
  ```json
  {
    "name": "etch-chat-frontend",
    "private": true,
    "version": "0.1.0",
    "type": "module",
    "scripts": {
      "dev": "vite",
      "build": "tsc && vite build",
      "preview": "vite preview"
    },
    "dependencies": {
      "react": "^18.2.0",
      "react-dom": "^18.2.0"
    },
    "devDependencies": {
      "@types/react": "^18.2.66",
      "@types/react-dom": "^18.2.22",
      "@vitejs/plugin-react": "^4.2.1",
      "typescript": "^5.2.2",
      "vite": "^5.2.0"
    }
  }
  ```

- [ ] **Step 2: Create vite.config.ts**
  Create `web/frontend/vite.config.ts` configuring a proxy to redirect API calls to FastAPI running on port 8000:
  ```typescript
  import { defineConfig } from 'vite';
  import react from '@vitejs/plugin-react';

  export default defineConfig({
    plugins: [react()],
    server: {
      port: 3000,
      proxy: {
        '/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
        '/static': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        }
      }
    }
  });
  ```

- [ ] **Step 3: Create tsconfig.json**
  Create `web/frontend/tsconfig.json`:
  ```json
  {
    "compilerOptions": {
      "target": "ES2020",
      "useDefineForClassFields": true,
      "lib": ["DOM", "DOM.Iterable", "ScriptHost", "ES2020"],
      "module": "ESNext",
      "skipLibCheck": true,

      /* Bundler mode */
      "moduleResolution": "bundler",
      "allowImportingTsExtensions": true,
      "resolveJsonModule": true,
      "isolatedModules": true,
      "noEmit": true,
      "jsx": "react-jsx",

      /* Linting */
      "strict": true,
      "noUnusedLocals": true,
      "noUnusedParameters": true,
      "noImplicitReturns": true,
      "noFallthroughCasesInSwitch": true
    },
    "include": ["src"]
  }
  ```

- [ ] **Step 4: Create index.html**
  Create `web/frontend/index.html` loading the Outfit & Inter Google Fonts:
  ```html
  <!doctype html>
  <html lang="en">
    <head>
      <meta charset="UTF-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <title>etch — Interactive Diagram Dashboard</title>
      <link rel="preconnect" href="https://fonts.googleapis.com">
      <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
      <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet">
    </head>
    <body style="margin: 0; background-color: #0a0b0d;">
      <div id="root"></div>
      <script type="module" src="/src/main.tsx"></script>
    </body>
  </html>
  ```

- [ ] **Step 5: Create main.tsx**
  Create `web/frontend/src/main.tsx`:
  ```typescript
  import React from 'react';
  import ReactDOM from 'react-dom/client';
  import App from './App.tsx';
  import './index.css';

  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
  ```

- [ ] **Step 6: Commit changes**
  ```bash
  git add web/frontend/package.json web/frontend/vite.config.ts web/frontend/tsconfig.json web/frontend/index.html web/frontend/src/main.tsx
  git commit -m "feat: scaffold vite + react + typescript frontend client with API proxies"
  ```

---

### Task 5: CSS Design System, Typography & Layout Setup

**Files:**
- Create: `web/frontend/src/index.css`

- [ ] **Step 1: Write Custom Premium Glassmorphic Design CSS**
  Create `web/frontend/src/index.css` with responsive columns, custom HSL design variables, glowing loaders, scrollbar styling, and smooth animations:
  ```css
  :root {
    --bg-main: #0a0b0d;
    --bg-pane: rgba(18, 20, 24, 0.6);
    --border-color: rgba(255, 255, 255, 0.05);
    --border-focus: rgba(139, 92, 246, 0.4);
    --glass-bg: rgba(255, 255, 255, 0.02);
    --text-primary: #f3f4f6;
    --text-secondary: #9ca3af;
    --text-muted: #6b7280;
    --accent-violet: #8b5cf6;
    --accent-teal: #14b8a6;
    --accent-gradient: linear-gradient(135deg, #8b5cf6 0%, #14b8a6 100%);
    --font-outfit: 'Outfit', sans-serif;
    --font-inter: 'Inter', sans-serif;
    --shadow-glow: 0 0 20px rgba(139, 92, 246, 0.15);
  }

  body {
    font-family: var(--font-inter);
    color: var(--text-primary);
    background-color: var(--bg-main);
    overflow: hidden;
    height: 100vh;
    width: 100vw;
  }

  .dashboard-container {
    display: grid;
    grid-template-columns: 40% 60%;
    height: 100vh;
    width: 100vw;
    background-color: var(--bg-main);
  }

  .panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    border-right: 1px solid var(--border-color);
    background: var(--bg-pane);
    backdrop-filter: blur(12px);
    overflow: hidden;
  }

  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 24px;
    border-bottom: 1px solid var(--border-color);
  }

  .panel-header h2 {
    font-family: var(--font-outfit);
    font-size: 1.25rem;
    font-weight: 600;
    margin: 0;
    background: var(--accent-gradient);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }

  /* Messages & Chat Feed */
  .chat-feed {
    flex: 1;
    overflow-y: auto;
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .chat-message {
    max-width: 85%;
    padding: 14px 18px;
    border-radius: 12px;
    line-height: 1.5;
    font-size: 0.925rem;
    word-break: break-word;
  }

  .chat-message.user {
    align-self: flex-end;
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid var(--border-color);
  }

  .chat-message.assistant {
    align-self: flex-start;
    background-color: var(--glass-bg);
    border: 1px solid var(--border-color);
    border-left: 3px solid var(--accent-violet);
    box-shadow: var(--shadow-glow);
  }

  /* Glowing Indicator */
  .pulse-indicator {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-family: var(--font-outfit);
    font-size: 0.85rem;
    color: var(--accent-teal);
    font-weight: 500;
  }

  .pulse-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background-color: var(--accent-teal);
    box-shadow: 0 0 8px var(--accent-teal);
    animation: pulse 1.5s infinite ease-in-out;
  }

  @keyframes pulse {
    0%, 100% { opacity: 0.4; transform: scale(0.9); }
    50% { opacity: 1; transform: scale(1.1); }
  }

  /* Input panel styling */
  .chat-input-area {
    padding: 16px 24px 24px;
    border-top: 1px solid var(--border-color);
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .quick-pills {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    scrollbar-width: none;
  }
  .quick-pills::-webkit-scrollbar { display: none; }

  .pill-btn {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid var(--border-color);
    color: var(--text-secondary);
    padding: 6px 12px;
    border-radius: 16px;
    font-size: 0.75rem;
    cursor: pointer;
    font-family: var(--font-inter);
    transition: all 0.2s ease;
  }
  .pill-btn:hover {
    background: rgba(139, 92, 246, 0.1);
    border-color: var(--accent-violet);
    color: var(--text-primary);
  }

  .input-wrapper {
    display: flex;
    gap: 12px;
    background: rgba(0, 0, 0, 0.2);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 6px 12px;
    transition: border-color 0.2s;
  }
  .input-wrapper:focus-within {
    border-color: var(--border-focus);
    box-shadow: var(--shadow-glow);
  }

  .text-input {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    color: var(--text-primary);
    font-family: var(--font-inter);
    font-size: 0.9rem;
    resize: none;
    height: 24px;
  }

  .send-btn {
    background: var(--accent-gradient);
    border: none;
    color: white;
    border-radius: 6px;
    padding: 6px 14px;
    font-family: var(--font-outfit);
    font-weight: 500;
    font-size: 0.85rem;
    cursor: pointer;
    transition: opacity 0.2s;
  }
  .send-btn:hover { opacity: 0.9; }
  .send-btn:disabled { background: var(--text-muted); cursor: not-allowed; }

  /* Right Panel: Canvas styling */
  .canvas-view {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    padding: 32px;
    position: relative;
    background: radial-gradient(circle at center, rgba(18, 20, 24, 0.3) 0%, var(--bg-main) 100%);
    overflow: hidden;
  }

  .canvas-inner {
    max-width: 100%;
    max-height: 70%;
    border-radius: 12px;
    border: 1px solid var(--border-color);
    box-shadow: var(--shadow-glow);
    overflow: hidden;
    position: relative;
  }

  .canvas-inner img {
    display: block;
    width: 100%;
    height: auto;
    object-fit: contain;
  }

  .canvas-overlay-btn {
    position: absolute;
    top: 12px;
    right: 12px;
    display: flex;
    gap: 8px;
    opacity: 0;
    transition: opacity 0.2s;
  }
  .canvas-inner:hover .canvas-overlay-btn { opacity: 1; }

  .action-btn {
    background: rgba(10, 11, 13, 0.8);
    backdrop-filter: blur(4px);
    border: 1px solid var(--border-color);
    color: var(--text-primary);
    padding: 8px;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .action-btn:hover {
    border-color: var(--accent-teal);
    color: var(--accent-teal);
  }

  /* History Gallery Panel */
  .gallery-pane {
    height: 160px;
    border-top: 1px solid var(--border-color);
    padding: 16px 24px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    background: rgba(18, 20, 24, 0.4);
  }

  .gallery-title {
    font-family: var(--font-outfit);
    font-size: 0.85rem;
    color: var(--text-secondary);
    font-weight: 500;
  }

  .gallery-items {
    display: flex;
    gap: 16px;
    overflow-x: auto;
    padding-bottom: 8px;
  }

  .gallery-item {
    flex-shrink: 0;
    width: 150px;
    height: 85px;
    border-radius: 6px;
    border: 1px solid var(--border-color);
    overflow: hidden;
    cursor: pointer;
    transition: all 0.2s;
  }
  .gallery-item:hover, .gallery-item.active {
    border-color: var(--accent-violet);
    box-shadow: 0 0 10px rgba(139, 92, 246, 0.3);
    transform: translateY(-2px);
  }

  .gallery-item img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  /* Custom Sidebar Settings panel drawer */
  .settings-btn {
    background: transparent;
    border: 1px solid var(--border-color);
    color: var(--text-secondary);
    padding: 6px 12px;
    border-radius: 6px;
    cursor: pointer;
    font-family: var(--font-outfit);
    font-size: 0.85rem;
    transition: all 0.2s;
  }
  .settings-btn:hover {
    border-color: var(--accent-teal);
    color: var(--accent-teal);
  }

  .drawer-overlay {
    position: fixed;
    top: 0;
    right: 0;
    width: 320px;
    height: 100vh;
    background: rgba(10, 11, 13, 0.95);
    border-left: 1px solid var(--border-color);
    box-shadow: -10px 0 30px rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(20px);
    z-index: 100;
    display: flex;
    flex-direction: column;
    padding: 24px;
    transform: translateX(100%);
    transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  }
  .drawer-overlay.open { transform: translateX(0); }

  .settings-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 20px;
  }

  .settings-group label {
    font-family: var(--font-outfit);
    font-size: 0.8rem;
    color: var(--text-secondary);
    font-weight: 500;
  }

  .settings-input, .settings-select {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid var(--border-color);
    color: var(--text-primary);
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 0.85rem;
    outline: none;
  }
  .settings-input:focus, .settings-select:focus {
    border-color: var(--accent-teal);
  }

  ::-webkit-scrollbar {
    width: 6px;
    height: 6px;
  }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.1);
    border-radius: 3px;
  }
  ::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.2); }
  ```

- [ ] **Step 2: Commit changes**
  ```bash
  git add web/frontend/src/index.css
  git commit -m "feat: design comprehensive premium glassmorphic dark-mode CSS system"
  ```

---

### Task 6: Frontend Components (Chat, Canvas & Settings)

**Files:**
- Create: `web/frontend/src/components/ChatPanel.tsx`
- Create: `web/frontend/src/components/CanvasPanel.tsx`

- [ ] **Step 1: Implement Chat Panel Component**
  Create `web/frontend/src/components/ChatPanel.tsx` with messaging thread lists, dynamic pulsing loading states, auto-scrolling triggers, and common pills:
  ```typescript
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
  ```

- [ ] **Step 2: Implement Canvas Panel & Settings Drawer Component**
  Create `web/frontend/src/components/CanvasPanel.tsx` with high-res active canvas, slide-out configuration tray, copy to clipboard trigger, and responsive history gallery layout:
  ```typescript
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
    };
    onChangeConfig: (key: string, value: string) => void;
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

          <div className="settings-group">
            <label>Active Codebase Absolute Path</label>
            <input
              type="text"
              className="settings-input"
              value={config.codebase_path}
              onChange={(e) => onChangeConfig('codebase_path', e.target.value)}
              placeholder="/Users/username/project"
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
  ```

- [ ] **Step 3: Commit changes**
  ```bash
  git add web/frontend/src/components/ChatPanel.tsx web/frontend/src/components/CanvasPanel.tsx
  git commit -m "feat: implement Chat Panel, Interactive Canvas and drawing configurations drawer"
  ```

---

### Task 7: Main App State Coordinator & SSE Orchestration

**Files:**
- Create: `web/frontend/src/App.tsx`

- [ ] **Step 1: Write State, SSE Handshake, and History Refresh logic**
  Create `web/frontend/src/App.tsx` to handle HTTP requests, instantiate EventSource for real-time progress updates, manage loading toggles, and coordinate history updates:
  ```typescript
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
  ```

- [ ] **Step 2: Commit changes**
  ```bash
  git add web/frontend/src/App.tsx
  git commit -m "feat: connect frontend with backend SSE event source and coordinate main application state"
  ```
