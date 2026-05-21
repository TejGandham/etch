import os
from pathlib import Path
from typing import Optional
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

