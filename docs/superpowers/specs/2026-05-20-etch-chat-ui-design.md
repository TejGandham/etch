# Etch Chat UI Design Spec

A premium, local web-based chat interface and dashboard for **etch** that allows users to generate and refine diagrams through a conversational chat interface while automatically pulling context from their local codebase on disk.

- **Date**: 2026-05-20
- **Author**: Antigravity AI
- **Status**: Approved / Draft

---

## 1. System Architecture

The application is structured as a lightweight full-stack application running entirely locally on the user's machine.

```
       +---------------------------------------+
       |         Vite + React (SPA)            |
       |  (Sleek dark glassmorphic dashboard)  |
       +-------------------+-------------------+
                           │
       HTTP / SSE (APIs)   │   Static Images (/static)
                           ▼
       +-------------------+-------------------+
       |          FastAPI Backend              |
       |  (Runs local server on port 8000)     |
       +-------+-----------------------+-------+
               │                       │
               ▼                       ▼
      [ Local Filesystem ]     [ Gemini GenAI API ]
   (Codebase scanning & PNGs)   (Reuses etch.py core)
```

### Stack Components:
1.  **Frontend**: Vite + React + TypeScript + Vanilla CSS (harmonious HSL variables, dark glassmorphism design, Outfit & Inter fonts).
2.  **Backend**: FastAPI + Pydantic (Python 3), reusing the async prompt-building and image-generation core from `etch.py`.
3.  **Communication**: Server-Sent Events (SSE) via `sse-starlette` for real-time progress stream, standard REST for static image access, settings, and job history.
4.  **Security / API Key**: Backend retrieves `GOOGLE_API_KEY` from the system environment variable or a local `.env` file.

---

## 2. Local Codebase Context Extraction

To allow users to say "draw a diagram of the auth system in this codebase," the backend has direct, local read-only access to the filesystem.

### 2.1 Active Codebase Selection
*   By default, the backend scans the directory in which it was launched.
*   The frontend settings panel provides a text input where the user can set or change the **Active Codebase Path** to any absolute directory on their disk (e.g., `/Users/tej/projects/my-web-app`).

### 2.2 Extraction Logic
When a user submits a prompt:
1.  **Tree Scan**: The backend performs a fast, non-blocking scan of the active codebase directory. It skips folders defined in a default ignore list (e.g., `.git`, `node_modules`, `venv`, `dist`, `build`, `.gemini`) and respects basic `.gitignore` rules.
2.  **File Hierarchy Summary**: It builds a lightweight structural map of the codebase (e.g., a text-based tree structure of important directories and source files).
3.  **Key File Reads**: It automatically reads primary configuration and documentation files if they exist (e.g., `README.md`, `package.json`, `requirements.txt`, `pyproject.toml`) to learn the technology stack and purpose of the project.
4.  **Targeted Source Scan (Heuristics)**: If the prompt contains keywords related to specific system parts (e.g., `auth`, `database`, `api`, `routing`), the backend searches for files with matching names and reads their exports, classes, or structure to extract code context.
5.  **Rich Prompt Assembly**: The extracted metadata and file structures are appended to the Gemini prompt behind the scenes, ensuring the model has full knowledge of the codebase context before generating the diagram.

---

## 3. Backend REST & SSE Endpoints

Reusing `etch.py`'s core functions, the FastAPI backend will expose the following endpoints:

### 3.1 Schemas (Pydantic)
```python
from pydantic import BaseModel
from typing import Optional

class DiagramRequest(BaseModel):
    description: str
    aspect_ratio: str = "16:9"
    resolution: str = "2K"
    audience: Optional[str] = None
    codebase_path: Optional[str] = None

class DiagramItem(BaseModel):
    id: str
    prompt: str
    audience: Optional[str]
    aspect_ratio: str
    resolution: str
    imageUrl: str
    created_at: str
```

### 3.2 Endpoint Signatures
*   `POST /api/jobs`: Start a diagram generation job.
    *   Accepts `DiagramRequest`.
    *   Reads and processes the codebase context if `codebase_path` is specified.
    *   Fires up a background generation task (reusing `etch.py`'s thread orchestration).
    *   Returns `{"job_id": "..."}` immediately.
*   `GET /api/jobs/stream/{job_id}`: Real-time Server-Sent Events (SSE) status stream.
    *   Monitors the active job's status and yields standard `text/event-stream` messages:
        *   `event: status`, `data: {"status": "queued"}`
        *   `event: status`, `data: {"status": "generating"}`
        *   `event: status`, `data: {"status": "complete", "imageUrl": "/static/diagram_abc.png"}`
        *   `event: status`, `data: {"status": "failed", "error": "..."}`
*   `GET /api/history`: Reads the output directory to compile a list of all previously generated PNGs and their cached prompt metadata. Returns a list of `DiagramItem`.
*   `POST /api/config/scan`: Validates a local codebase path and returns its folder tree structure and detected language/framework.
*   `Mount /static`: Mounts the backend `output` directory as `/static` to serve generated images directly to the frontend.

---

## 4. Frontend UI Design

The UI is a premium, single-page split dashboard that fits entirely in the browser window without requiring scroll containers for the main layout.

### 4.1 Visual Styling (Vanilla CSS)
*   **Theme**: Cyberpunk-industrial minimal dark mode. Deep rich dark background `#0a0b0d`, card panel glassmorphism using semi-transparent white fills (`rgba(255, 255, 255, 0.03)`) with backdrop filters, and sharp glowing borders (`rgba(255, 255, 255, 0.05)`).
*   **Fonts**: *Outfit* (Google Fonts) for geometric, modern titles, and *Inter* for extremely readable chat bubbles and metadata labels.
*   **Accents**: Violet-to-teal linear gradients and glowing indicator LEDs for active SSE states.

### 4.2 Split-Pane Layout
*   **Left Panel (Width: 40%) - The Chat Feed**:
    *   **Chat History**: Minimalist message bubbles. User messages are styled with a clean gray border; Etch's responses are styled in a dark glass card with a glowing left border.
    *   **SSE Pulse Indicator**: During active generation, an animated pulsing loader showing real-time states (`[Step 1: Queued]` ➔ `[Step 2: Sketches in Progress...]`).
    *   **Input Bar**: Text area that submits prompts on press of `Enter`. Features quick-pill tags to append common audiences (e.g., `+ for PM`, `+ for Onboarding`, `+ for End-User`).
*   **Right Panel (Width: 60%) - Diagram Canvas & Gallery**:
    *   **Interactive Canvas**: Displays the currently selected diagram. Includes floating overlay buttons for **Download PNG**, **Copy Image to Clipboard**, and **Zoom Fullscreen**.
    *   **Configuration Drawer**: Slide-out drawer or header controls to adjust aspect ratio, resolution, target audience, and active codebase path.
    *   **Horizontal Gallery Tray**: A clean, responsive thumbnail gallery at the bottom representing past diagrams. Clicking a thumbnail smoothly switches the canvas view.

---

## 5. Verification Plan

### 5.1 Automated Server Tests
*   We will add test coverage to verify:
    *   Pydantic request payload validation.
    *   Active codebase scanning and tree hierarchy building (handling non-existent directories gracefully).
    *   SSE endpoint streaming sequence (mocking the generator thread).

### 5.2 Manual Browser Verification
*   We will spin up the server, navigate to the local client URL, and manually check:
    *   Creating a new diagram job and watching the SSE status timeline update live.
    *   Inputting a local path and prompting "Draw the module diagram" to verify context is injected.
    *   Hovering and executing Download/Copy controls on the canvas.
    *   Gallery navigation and configuration settings adjustment.
