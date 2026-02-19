#!/usr/bin/env python3
"""
AI Bridge for CICS AI Assistant
Provides HTTP endpoint for KICKS/CICS to query AI services

This bridge monitors for questions from MVS and returns AI responses.

Usage:
    python ai_bridge.py [--port 5000] [--ollama-url http://localhost:11434]
"""

import os
import sys
import time
import asyncio
import argparse
import logging
from datetime import datetime
from typing import Optional

# FastAPI imports
try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    import uvicorn
    import httpx
except ImportError:
    print("Required packages not found. Install with:")
    print("  pip install fastapi uvicorn httpx pydantic")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
MAX_RESPONSE_CHARS = 760  # 10 lines × 76 chars for 3270 screen
MAX_INPUT_CHARS = 72      # Single line input on 3270

# GPU-optimized Ollama options (populated at startup)
GPU_OLLAMA_OPTIONS = {}

# System prompt for mainframe context
SYSTEM_PROMPT = """You are an AI assistant helping mainframe operators and developers.
You are accessed through a CICS terminal on MVS 3.8j.
Keep responses concise (under 700 characters) and focused.
Use plain text only - no markdown, no special formatting.
Break long responses into short paragraphs.
Focus on practical, actionable information.
You understand JCL, COBOL, CICS, RACF, VSAM, and mainframe operations."""

# FastAPI app
app = FastAPI(
    title="AI Bridge for CICS",
    description="Provides AI capabilities to KICKS/CICS on MVS 3.8j",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class QuestionRequest(BaseModel):
    question: str
    context: Optional[str] = None


class AnswerResponse(BaseModel):
    answer: str
    timestamp: str
    model: str
    truncated: bool


def format_for_3270(text: str, max_chars: int = MAX_RESPONSE_CHARS) -> str:
    """
    Format AI response for 3270 terminal display.
    - Remove markdown formatting
    - Limit to max characters
    - Ensure proper line breaks
    """
    # Remove common markdown
    text = text.replace('**', '')
    text = text.replace('*', '')
    text = text.replace('`', '')
    text = text.replace('#', '')
    
    # Normalize whitespace
    lines = text.split('\n')
    formatted_lines = []
    
    for line in lines:
        line = line.strip()
        if line:
            # Wrap long lines at 76 characters
            while len(line) > 76:
                # Find last space before 76
                split_pos = line[:76].rfind(' ')
                if split_pos == -1:
                    split_pos = 76
                formatted_lines.append(line[:split_pos])
                line = line[split_pos:].strip()
            formatted_lines.append(line)
    
    # Join and truncate
    result = '\n'.join(formatted_lines)
    
    truncated = len(result) > max_chars
    if truncated:
        result = result[:max_chars-3] + '...'
    
    return result, truncated


async def query_ollama(question: str, context: str = None) -> str:
    """Query Ollama for AI response."""
    
    # Build prompt
    if context:
        prompt = f"Context: {context}\n\nQuestion: {question}"
    else:
        prompt = question
    
    # Build options: start with GPU-optimized base, then override per-request
    options = dict(GPU_OLLAMA_OPTIONS)
    options["temperature"] = 0.7
    options["num_predict"] = 256  # Keep responses short for 3270
    
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": options,
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "No response from AI")
    except httpx.TimeoutException:
        return "AI service timeout. Please try again."
    except httpx.HTTPError as e:
        logger.error(f"Ollama HTTP error: {e}")
        return f"AI service error: {str(e)[:50]}"
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        return "AI service unavailable."


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "AI Bridge for CICS",
        "status": "running",
        "ollama_url": OLLAMA_URL,
        "model": OLLAMA_MODEL,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health")
async def health():
    """Detailed health check."""
    # Check Ollama connectivity
    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            ollama_ok = resp.status_code == 200
    except:
        pass
    
    return {
        "status": "healthy" if ollama_ok else "degraded",
        "ollama_connected": ollama_ok,
        "ollama_url": OLLAMA_URL,
        "model": OLLAMA_MODEL
    }


@app.post("/api/ask", response_model=AnswerResponse)
async def ask_question(request: QuestionRequest):
    """
    Main endpoint for CICS to submit questions.
    
    Request:
        question: str - The user's question (max 72 chars from 3270)
        context: str - Optional context information
    
    Response:
        answer: str - AI response formatted for 3270 (max 760 chars)
        timestamp: str - ISO timestamp
        model: str - Model used
        truncated: bool - Whether response was truncated
    """
    # Validate input
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    
    # Limit input length
    if len(question) > MAX_INPUT_CHARS:
        question = question[:MAX_INPUT_CHARS]
    
    logger.info(f"Question received: {question[:50]}...")
    
    # Query AI
    raw_response = await query_ollama(question, request.context)
    
    # Format for 3270
    formatted_response, truncated = format_for_3270(raw_response)
    
    logger.info(f"Response: {len(formatted_response)} chars, truncated={truncated}")
    
    return AnswerResponse(
        answer=formatted_response,
        timestamp=datetime.now().isoformat(),
        model=OLLAMA_MODEL,
        truncated=truncated
    )


@app.post("/api/ask/simple")
async def ask_simple(question: str):
    """
    Simple GET-style endpoint for testing.
    Returns plain text response suitable for direct use.
    """
    if not question:
        return "ERROR: No question provided"
    
    raw_response = await query_ollama(question)
    formatted_response, _ = format_for_3270(raw_response)
    
    return formatted_response


# ============================================================================
# TD Queue Bridge (for direct CICS integration)
# ============================================================================

# In-memory queues simulating TD queues
question_queue = asyncio.Queue()
response_queue = asyncio.Queue()


@app.post("/api/queue/question")
async def queue_question(question: str):
    """
    Receive question from CICS TD queue bridge.
    Used when CICS writes to extrapartition TD queue.
    """
    await question_queue.put({
        "question": question,
        "timestamp": datetime.now().isoformat()
    })
    return {"status": "queued", "queue_size": question_queue.qsize()}


@app.get("/api/queue/response")
async def get_response():
    """
    Get response for CICS TD queue bridge.
    Used when CICS reads from response TD queue.
    """
    try:
        response = response_queue.get_nowait()
        return response
    except asyncio.QueueEmpty:
        return {"status": "empty"}


async def process_queue():
    """Background task to process queued questions."""
    while True:
        try:
            item = await asyncio.wait_for(question_queue.get(), timeout=1.0)
            question = item["question"]
            
            logger.info(f"Processing queued question: {question[:50]}...")
            
            raw_response = await query_ollama(question)
            formatted_response, truncated = format_for_3270(raw_response)
            
            await response_queue.put({
                "answer": formatted_response,
                "timestamp": datetime.now().isoformat(),
                "truncated": truncated
            })
            
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            logger.error(f"Queue processing error: {e}")


@app.on_event("startup")
async def startup():
    """Start background queue processor and detect GPU."""
    global OLLAMA_MODEL, GPU_OLLAMA_OPTIONS
    
    # Detect GPU and auto-configure
    try:
        from app.gpu import get_gpu_info, get_recommended_model, get_gpu_ollama_options
        gpu = get_gpu_info()
        if gpu.is_available:
            GPU_OLLAMA_OPTIONS = get_gpu_ollama_options(gpu)
            # Auto-select model if not explicitly set via env
            if not os.getenv("OLLAMA_MODEL"):
                OLLAMA_MODEL = get_recommended_model(gpu)
            logger.info(
                f"GPU detected: {gpu.name} ({gpu.vram_total_gb}GB) — "
                f"Tier: {gpu.tier} — Model: {OLLAMA_MODEL}"
            )
        else:
            logger.info("No GPU detected — using CPU inference")
    except Exception as e:
        logger.info(f"GPU detection skipped: {e}")
    
    asyncio.create_task(process_queue())
    logger.info(f"AI Bridge started - Ollama: {OLLAMA_URL}, Model: {OLLAMA_MODEL}")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="AI Bridge for CICS")
    parser.add_argument("--port", type=int, default=5050, help="Port to listen on")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama API URL")
    parser.add_argument("--model", default="llama3.1:8b", help="Ollama model to use")
    
    args = parser.parse_args()
    
    # Use args values
    global OLLAMA_URL, OLLAMA_MODEL
    OLLAMA_URL = args.ollama_url
    OLLAMA_MODEL = args.model
    
    # Detect GPU for banner
    gpu_line = "GPU: Not detected"
    try:
        from app.gpu import get_gpu_info
        gpu = get_gpu_info()
        if gpu.is_available:
            gpu_line = f"GPU: {gpu.name} ({gpu.vram_total_gb}GB VRAM) — Tier: {gpu.tier.upper()}"
    except Exception:
        pass
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║           AI Bridge for CICS / MVS 3.8j                      ║
╠══════════════════════════════════════════════════════════════╣
║  Endpoint:  http://{args.host}:{args.port}/api/ask
║  Ollama:    {OLLAMA_URL}
║  Model:     {OLLAMA_MODEL}
║  {gpu_line}
╚══════════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
