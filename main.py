from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import shutil
import os
import uuid
from vision_extractor import extract_text_from_file
from rag_service import RAGService

app = FastAPI(title="GST RAG API")

# Read allowed origins from env for deployment flexibility
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rag_service = None

# Simple in-memory store for jobs
jobs: Dict[str, Any] = {}

SUPPORTED_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif", ".webp",
    ".pdf", ".docx", ".doc", ".pptx", ".ppt",
    ".xlsx", ".xls", ".csv",
    ".txt", ".md", ".html", ".htm", ".xml", ".rtf", ".eml", ".msg"
}

@app.on_event("startup")
def startup_event():
    global rag_service
    try:
        rag_service = RAGService()
        print("RAG Service initialized successfully.")
    except Exception as e:
        print(f"Failed to initialize RAG Service: {e}.")

def process_batch_job(job_id: str, file_paths: List[str], original_filenames: List[str]):
    jobs[job_id]["status"] = "processing"

    total_chunks = 0
    results = []

    for i, file_path in enumerate(file_paths):
        filename = original_filenames[i]
        try:
            # Check file extension
            ext = os.path.splitext(filename)[1].lower()
            if ext not in SUPPORTED_EXTENSIONS:
                results.append({
                    "filename": filename,
                    "status": "error",
                    "message": f"Unsupported file type: {ext}"
                })
                continue

            # Extract text using universal extractor
            extracted_text = extract_text_from_file(file_path)

            if not extracted_text.strip():
                results.append({
                    "filename": filename,
                    "status": "error",
                    "message": "No text could be extracted from this file."
                })
                continue

            # Ingest (automatically deletes old data for this source first)
            num_chunks = rag_service.ingest_text(extracted_text, metadata={"source": filename})
            total_chunks += num_chunks
            results.append({"filename": filename, "status": "success", "chunks": num_chunks})

        except Exception as e:
            results.append({"filename": filename, "status": "error", "message": str(e)})
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)

        # Update live progress
        jobs[job_id]["progress"] = int(((i + 1) / len(file_paths)) * 100)
        jobs[job_id]["current_file"] = f"{i+1} of {len(file_paths)}"

    jobs[job_id]["status"] = "completed"
    jobs[job_id]["results"] = results
    jobs[job_id]["total_chunks_ingested"] = total_chunks


@app.post("/upload/batch")
async def upload_batch(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    """Start an asynchronous batch ingestion job."""
    if not rag_service:
        raise HTTPException(status_code=500, detail="RAG Service not initialized.")

    os.makedirs("temp_uploads", exist_ok=True)

    job_id = str(uuid.uuid4())
    file_paths = []
    original_filenames = []

    for file in files:
        file_path = f"temp_uploads/{job_id}_{file.filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        file_paths.append(file_path)
        original_filenames.append(file.filename)

    jobs[job_id] = {
        "status": "queued",
        "progress": 0,
        "total_files": len(files),
        "current_file": f"0 of {len(files)}"
    }

    background_tasks.add_task(process_batch_job, job_id, file_paths, original_filenames)
    return {"job_id": job_id, "status": "queued"}


@app.get("/upload/status/{job_id}")
async def get_job_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


class QueryRequest(BaseModel):
    question: str


@app.post("/chat")
async def chat(request: QueryRequest):
    if not rag_service:
        raise HTTPException(status_code=500, detail="RAG Service not initialized.")
    try:
        answer = rag_service.query(request.question)
        return {"question": request.question, "answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok", "rag_ready": rag_service is not None}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8923)))
