from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
import uvicorn
import shutil
import os
import json
from glob import glob
from pypdf import PdfReader

PROJECTS_DIR = "projects"
if not os.path.exists(PROJECTS_DIR):
    os.makedirs(PROJECTS_DIR)

import sys
import os

# Ensure backend directory is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from nlp_engine import nlp_engine
import toon
import memory

# Import the INSTANCE from ollama_client.py which wraps LLMClient
try:
    from ollama_client import ollama_client
except ImportError:
    from backend.ollama_client import ollama_client



app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def extract_text_from_file(file_path: str, filename: str) -> str:
    text = ""
    if filename.endswith(".pdf"):
        try:
            reader = PdfReader(file_path)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        except Exception as e:
            print(f"Error reading PDF: {e}")
            return ""
    else:
        # Assume text
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        except UnicodeDecodeError:
             # Try latin-1 fallback
            with open(file_path, "r", encoding="latin-1") as f:
                text = f.read()
    
    # Clean BOM and common artifacts
    text = text.replace('\ufeff', '')
    return text

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.post("/api/config")
async def update_config(data: dict):
    """
    Update LLM configuration from frontend.
    Handles provider, api_key, model, etc.
    """
    ollama_client.update_config(
        provider=data.get("provider"),
        model=data.get("model"),
        base_url=data.get("url") or data.get("base_url"),
        api_key=data.get("api_key"),
        ctx=data.get("ctx"),
        timeout=data.get("timeout"),
        keep_alive=data.get("keep_alive")
    )
    return JSONResponse({"status": "updated", "config": data})

@app.post("/analyze")
async def analyze_text(file: UploadFile = File(...)):
    temp_filename = f"temp_{file.filename}"
    try:
        with open(temp_filename, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        text = extract_text_from_file(temp_filename, file.filename)
        
        if not text:
             raise HTTPException(status_code=400, detail="Could not extract text from file.")
        
        # Analyze text
        characters = nlp_engine.extract_characters(text)
        characters = nlp_engine.extract_characters(text)
        world_elements = nlp_engine.extract_world_elements(text)
        glossary = nlp_engine.extract_glossary_terms(text)
        
        return JSONResponse(content={
            "filename": file.filename,
            "characters": characters,
            "world": world_elements,
            "glossary": glossary,
            "text": text,  # Include text for synopsis generation
            "message": "Analysis processing complete"
        })
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

@app.post("/refine")
async def refine_analysis(data: dict):
    # Expects {"characters": [...]}
    char_list = data.get("characters", [])
    print(f"Received refinement request for {len(char_list)} characters")
    
    refined_list = ollama_client.refine_characters(char_list)
    
    return JSONResponse(content={"characters": refined_list})

@app.post("/refine_stream")
async def refine_stream(data: dict):
    """Streaming refinement with progress updates."""
    char_list = data.get("characters", [])
    mode = data.get("mode", "characters")
    
    print(f"Streaming refine request for {len(char_list)} items (mode: {mode})")
    
    def generate():
        progress_updates = []
        results = []
        
        def on_progress(update):
            progress_updates.append(update)
        
        # Process with progress tracking
        if mode == "characters":
            batch_size = 6
            total_batches = (len(char_list) - 1) // batch_size + 1 if char_list else 0
            
            for i in range(0, max(1, len(char_list)), batch_size):
                batch_num = i // batch_size + 1
                progress = int((batch_num / total_batches) * 90) if total_batches > 0 else 50
                
                # Send progress update
                yield json.dumps({
                    "type": "progress",
                    "batch": batch_num,
                    "total": total_batches,
                    "progress": progress,
                    "message": f"Batch {batch_num}/{total_batches}..."
                }) + "\n"
            
            # Actually process
            results = ollama_client.refine_characters(char_list)
        
        # Final result
        yield json.dumps({"type": "complete", "characters": results, "progress": 100}) + "\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


@app.post("/refine_world")
async def refine_world_analysis(data: dict):
    # Expects {"world": [...]}
    world_list = data.get("world", [])
    print(f"Received WORLD refinement request for {len(world_list)} items")
    
    refined_list = ollama_client.refine_world_elements(world_list)
    
    return JSONResponse(content={"world": refined_list})

@app.post("/refine_glossary")
async def refine_glossary_analysis(data: dict):
    # Expects {"glossary": [...]}
    glossary_list = data.get("glossary", [])
    print(f"Received GLOSSARY refinement request for {len(glossary_list)} items")
    
    refined_list = ollama_client.refine_glossary(glossary_list)
    
    return JSONResponse(content={"glossary": refined_list})

@app.post("/api/synopsis")
async def generate_synopsis(data: dict):
    """Generate POST synopses from manuscript text."""
    text = data.get("text", "")
    num_posts = data.get("num_posts", 5)
    
    if not text:
        raise HTTPException(status_code=400, detail="No text provided")
    
    print(f"Generating {num_posts} synopses from {len(text)} chars")
    
    synopses = ollama_client.generate_synopsis(text, num_posts=num_posts)
    
    return JSONResponse(content={"synopses": synopses})

@app.get("/api/config")
async def get_config():
    """Get current LLM configuration."""
    return JSONResponse(content={
        "model": ollama_client.model,
        "url": ollama_client.base_url,
        "ctx": ollama_client.ctx,
        "timeout": ollama_client.timeout
    })

@app.post("/api/config")
async def set_config(data: dict):
    """Update LLM configuration dynamically."""
    model = data.get("model")
    url = data.get("url")
    ctx = data.get("ctx")
    timeout = data.get("timeout")
    
    ollama_client.update_config(model=model, base_url=url, ctx=ctx, timeout=timeout)
    
    return JSONResponse(content={
        "status": "updated",
        "model": ollama_client.model,
        "url": ollama_client.base_url,
        "ctx": ollama_client.ctx,
        "timeout": ollama_client.timeout
    })

# ===================== MEMVID ENDPOINTS =====================

@app.post("/api/index")
async def index_manuscript(data: dict):
    """Index a manuscript for semantic search."""
    project_name = data.get("project", "default")
    text = data.get("text", "")
    
    if not text:
        raise HTTPException(status_code=400, detail="No text provided")
    
    project_dir = os.path.join(PROJECTS_DIR, project_name)
    if not os.path.exists(project_dir):
        os.makedirs(project_dir)
    
    mem = memory.get_memory(project_dir)
    
    if not mem.is_available():
        return JSONResponse(content={
            "status": "unavailable",
            "message": "MemVid not installed. Install with: pip install memvid"
        })
    
    try:
        chunks = mem.index_manuscript(text)
        return JSONResponse(content={
            "status": "indexed",
            "chunks": chunks,
            "message": f"Indexed {chunks} chunks"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/search")
async def search_manuscript(data: dict):
    """Search indexed manuscript."""
    project_name = data.get("project", "default")
    query = data.get("query", "")
    top_k = data.get("top_k", 5)
    
    project_dir = os.path.join(PROJECTS_DIR, project_name)
    mem = memory.get_memory(project_dir)
    
    if not mem.is_indexed():
        return JSONResponse(content={"results": [], "message": "Not indexed"})
    
    results = mem.search(query, top_k=top_k)
    return JSONResponse(content={"results": results})

@app.get("/api/memory/status")
async def memory_status():
    """Check MemVid availability."""
    return JSONResponse(content={
        "available": memory.MEMVID_AVAILABLE
    })

# ===================== TOON EXPORT =====================

@app.post("/api/export/toon")
async def export_toon(data: dict):
    """Export analysis data to TOON format."""
    characters = data.get("characters", [])
    world = data.get("world", [])
    glossary = data.get("glossary", [])
    synopses = data.get("synopses", [])
    title = data.get("title", "Untitled")
    
    bibbia_data = toon.to_bibbia_format(characters, world, synopses, title, glossary=glossary)
    # For a single file export, we combine them
    toon_content = bibbia_data["dna"] + "\n\n" + (bibbia_data["sinossi"] if synopses else "")
    
    return JSONResponse(content={
        "toon": toon_content,
        "characters_count": len(characters),
        "world_count": len(world),
        "synopses_count": len(synopses)
    })

@app.post("/api/bibbia/send")
async def send_to_bibbia(data: dict):
    """
    Invia dati BookAnalyzer a Sandbox-UI BIBBIA.
    Genera formato TOON e lo invia all'endpoint /bibbia/save.
    """
    import requests as http_requests
    
    characters = data.get("characters", [])
    world = data.get("world", [])
    glossary = data.get("glossary", [])
    synopses = data.get("synopses", [])
    title = data.get("title", "BookAnalyzer Export")
    sandbox_url = data.get("sandbox_url", "http://127.0.0.1:5000")
    
    # Genera contenuto BIBBIA
    bibbia_data = toon.to_bibbia_format(characters, world, synopses, title, glossary=glossary)
    dna_content = bibbia_data["dna"]
    sinossi_content = bibbia_data["sinossi"]
    
    # Prepara per merge con BIBBIA esistente (se presente)
    try:
        # Carica BIBBIA esistente per preservare eventuali note manuali
        load_resp = http_requests.get(f"{sandbox_url}/bibbia/load", timeout=5)
        existing_dna = ""
        if load_resp.ok:
            existing_data = load_resp.json()
            if existing_data.get("success"):
                existing_dna = existing_data.get("dna", "")
        
        # Merge DNA: appendi se esiste già
        if existing_dna.strip():
            merged_dna = existing_dna + "\n\n# === IMPORTATO DA BOOKANALYZER ===\n" + dna_content
        else:
            merged_dna = dna_content
        
        # Invia a BIBBIA con entrambi i campi
        save_resp = http_requests.post(
            f"{sandbox_url}/bibbia/save",
            json={
                "dna": merged_dna,
                "sinossi": sinossi_content
            },
            timeout=30
        )
        
        if save_resp.ok:
            result = save_resp.json()
            return JSONResponse(content={
                "success": True,
                "message": "Dati inviati a BIBBIA con successo",
                "tokens": result.get("tokens", 0),
                "characters_sent": len(characters),
                "world_sent": len(world),
                "synopses_sent": len(synopses)
            })
        else:
            return JSONResponse(content={
                "success": False,
                "error": f"Errore da Sandbox-UI: {save_resp.text}"
            }, status_code=500)
            
    except http_requests.ConnectionError:
        return JSONResponse(content={
            "success": False,
            "error": f"Impossibile connettersi a Sandbox-UI ({sandbox_url}). Assicurati che sia in esecuzione."
        }, status_code=503)
    except Exception as e:
        return JSONResponse(content={
            "success": False,
            "error": str(e)
        }, status_code=500)


@app.get("/api/projects")
async def list_projects():
    files = glob(os.path.join(PROJECTS_DIR, "*.json"))
    projects = []
    for f in files:
        stat = os.stat(f)
        projects.append({
            "name": os.path.basename(f),
            "updated": stat.st_mtime
        })
    return sorted(projects, key=lambda x: x['updated'], reverse=True)

@app.post("/api/save")
async def save_project(data: dict):
    # data expects {"title": "...", "characters": [...], "world": [...]}
    title = data.get("title", "Untitled").strip()
    # Sanitize title for filename
    safe_title = "".join([c for c in title if c.isalnum() or c in (' ', '_', '-')]).replace(" ", "_")
    if not safe_title:
        safe_title = "Untitled"
        
    filename = f"{safe_title}.json"
    filepath = os.path.join(PROJECTS_DIR, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    
    return {"status": "saved", "filename": filename}

@app.get("/api/projects/{filename}")
async def load_project(filename: str):
    safe_filename = os.path.basename(filename)
    filepath = os.path.join(PROJECTS_DIR, safe_filename)
    
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Project not found")
        
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

@app.delete("/api/projects/{filename}")
async def delete_project(filename: str):
    safe_filename = os.path.basename(filename)
    filepath = os.path.join(PROJECTS_DIR, safe_filename)
    
    if os.path.exists(filepath):
        os.remove(filepath)
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Project not found")

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

# Mount static files at /static
app.mount("/static", StaticFiles(directory="static"), name="static")

# ===================== PHASE 9 & 10 ENDPOINTS =====================

@app.get("/api/models")
async def get_models():
    """Restituisce la lista dei modelli disponibili dal provider corrente."""
    try:
        # Access client from wrapper instance
        models = ollama_client.client.list_models()
        return {"models": models}
    except Exception as e:
        return JSONResponse({"error": str(e), "models": []}, status_code=500)

@app.post("/api/segment")
async def segment_text(data: dict):
    """
    Divide il testo in chunk logici (Capitoli/POST) o fissi.
    """
    text = data.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="No text provided")
    
    import re
    chunks = []
    
    # 1. Tentativo Regex "POST X"
    post_pattern = re.compile(r'(POST\s+\d+.*?)(?=POST\s+\d+|$)', re.DOTALL | re.IGNORECASE)
    matches = list(post_pattern.finditer(text))
    
    if matches:
        for i, m in enumerate(matches):
            chunks.append({
                "id": i + 1,
                "title": m.group(1).split('\n')[0].strip()[:50], # Prima riga come titolo
                "text": m.group(1).strip()
            })
    else:
        # 2. Fallback: Split per lunghezza (es. 10k caratteri)
        max_len = 10000
        total_len = len(text)
        for i in range(0, total_len, max_len):
            chunk_text = text[i : i + max_len]
            # Cerca l'ultimo a capo per non troncare a metà frase
            last_newline = chunk_text.rfind('\n')
            if last_newline > max_len * 0.8: # Se c'è un a capo verso la fine
                chunk_text = chunk_text[:last_newline]
                # Adjust index for next loop? (Questo è un naive split, per ora va bene)
            
            chunks.append({
                "id": (i // max_len) + 1,
                "title": f"Segmento {(i // max_len) + 1}",
                "text": chunk_text
            })
            
    return {"chunks": chunks}

@app.post("/api/analyze_chunk")
async def analyze_chunk_endpoint(data: dict):
    """Analizza un singolo chunk."""
    text = data.get("text", "")
    mode = data.get("mode", "characters") # characters, world
    
    results = ollama_client.analyze_chunk(text, mode=mode)
    return {"results": results}

@app.post("/api/merge")
async def merge_results_endpoint(data: dict):
    """Consolida risultati parziali."""
    results = data.get("results", [])
    mode = data.get("mode", "characters")
    
    merged = ollama_client.merge_results(results, mode=mode)
    return {"results": merged}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8008, reload=True)
