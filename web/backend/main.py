import os
import sys
import json
import asyncio
import uuid
import base64
from pathlib import Path
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

# Load local environment variables from workspace root
load_dotenv(dotenv_path=Path(__file__).parent.parent.parent / ".env")
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

# Add parent directory to path to reuse etch.py
sys.path.append(str(Path(__file__).parent.parent.parent.resolve()))
import etch

app = FastAPI(title="Etch API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure output directory
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(OUTPUT_DIR)), name="static")

# Local active jobs in-memory cache
jobs_cache: dict[str, dict] = {}

class HealthResponse(BaseModel):
    status: str
    workspace: str

@app.get("/api/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="healthy",
        workspace=os.getcwd()
    )

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
    ignore_folders = {".git", "node_modules", "venv", "__pycache__", "dist", "build", ".gemini", "superpowers-temp", ".venv"}
    
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

class DiagramRequest(BaseModel):
    description: str
    aspect_ratio: str = "16:9"
    resolution: str = "2K"
    audience: Optional[str] = None
    codebase_path: Optional[str] = None
    model: str = etch.DEFAULT_MODEL
    reference_images: Optional[list[str]] = None

def execute_generation_task(job_id: str, req: DiagramRequest):
    try:
        jobs_cache[job_id]["status"] = "generating"
        
        # standard technical drawing directive
        drawing_prefix = "Generate a clear, high-quality, professional technical system architecture diagram of the following:"
        
        # Inject codebase context if supplied
        if req.codebase_path:
            folder = Path(req.codebase_path)
            if folder.exists():
                tree_text = build_file_tree(folder, max_depth=2)
                full_description = (
                    f"Generate a clear, high-quality, professional technical system architecture diagram of the following codebase structure and user requirements:\n\n"
                    f"[Local Codebase Structure]\n{tree_text}\n\n"
                    f"[User Description]\n{req.description}\n\n"
                    f"Instruction: Render the architecture and file layout of this codebase as a clean, labeled technical diagram illustrating '{req.description}'."
                )
            else:
                full_description = f"{drawing_prefix} {req.description}"
        else:
            full_description = f"{drawing_prefix} {req.description}"
        
        # Resolve the selected provider and reject unsupported size combos up front.
        try:
            provider = etch.resolve_provider(req.model)
            etch.validate_capabilities(provider, req.aspect_ratio, req.resolution)
        except ValueError as e:
            jobs_cache[job_id]["status"] = "failed"
            jobs_cache[job_id]["error"] = str(e)
            return

        api_key = os.environ.get(provider.key_env_var)
        if not api_key or api_key == "mock":
            # Fallback mock mode (dev: no key configured for the selected provider)
            import time
            time.sleep(1)
            file_path = OUTPUT_DIR / f"diagram_{datetime.now():%Y%m%d_%H%M%S}_{job_id[:8]}.png"
            DUMMY_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            file_path.write_bytes(base64.b64decode(DUMMY_PNG_B64))

            with etch._jobs_lock:
                etch._jobs[job_id] = {
                    "status": "complete",
                    "created": datetime.now(),
                    "file_path": str(file_path)
                }
            jobs_cache[job_id]["status"] = "complete"
            jobs_cache[job_id]["imageUrl"] = f"/static/{file_path.name}"
            return

        loaded_references = []
        if req.reference_images:
            try:
                loaded_references = etch._load_reference_images(req.reference_images, provider)
            except ValueError as e:
                jobs_cache[job_id]["status"] = "failed"
                jobs_cache[job_id]["error"] = str(e)
                return

        with etch._jobs_lock:
            etch._jobs[job_id] = {"status": "queued", "created": datetime.now()}

        # Run generator through the selected provider
        etch._run_generation(
            job_id=job_id,
            provider=provider,
            api_key=api_key,
            description=full_description,
            audience=req.audience,
            aspect_ratio=req.aspect_ratio,
            resolution=req.resolution,
            output_dir=OUTPUT_DIR,
            reference_images=loaded_references
        )
        
        # Check output
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
        "model": req.model,
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
                yield {"event": "status", "data": json.dumps(payload)}
                
            if current_status in ("complete", "failed"):
                break
                
            await asyncio.sleep(0.5)
            
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
                "model": job.get("model"),
                "imageUrl": job["imageUrl"],
                "created_at": job["created_at"]
            })
    return history_items


