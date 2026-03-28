#!/usr/bin/env python3
"""
RAG Engine for Mainframe AI Assistant
Simple file-based implementation using Ollama embeddings
No external vector DB required!
"""

import os
import re
import json
import hashlib
import time
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
import httpx

# Try to import PDF support
try:
    from PyPDF2 import PdfReader
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAG_DIR = os.path.join(BASE_DIR, "data", "rag_data")
INDEX_FILE = os.path.join(RAG_DIR, "index.json")
EMBEDDINGS_FILE = os.path.join(RAG_DIR, "embeddings.json")
DOCS_DIR = os.path.join(RAG_DIR, "documents")

# Create directories
os.makedirs(RAG_DIR, exist_ok=True)
os.makedirs(DOCS_DIR, exist_ok=True)

# Ollama embedding endpoint
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBEDDING_MODEL = "nomic-embed-text"


@dataclass
class Document:
    """Represents a document in the RAG system"""
    id: str
    name: str
    source: str
    doc_type: str
    chunks: int
    added: str


class SentenceChunker:
    """Sentence-aware text chunker that respects sentence boundaries"""

    def __init__(self, target_size: int = 400, max_size: int = 600, overlap_sentences: int = 1):
        self.target_size = target_size
        self.max_size = max_size
        self.overlap_sentences = overlap_sentences
        # Pattern to split on sentence endings followed by space and capital letter
        self.sentence_pattern = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')

    def chunk(self, text: str) -> List[str]:
        """Split text into chunks respecting sentence boundaries"""
        # Split into sentences
        sentences = self.sentence_pattern.split(text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return []

        chunks = []
        current_chunk = []
        current_size = 0

        for sentence in sentences:
            sentence_len = len(sentence.split())

            # If single sentence exceeds max_size, split it by words
            if sentence_len > self.max_size:
                # Flush current chunk first
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
                    current_size = 0

                # Split long sentence into word chunks
                words = sentence.split()
                for i in range(0, len(words), self.target_size):
                    chunk_words = words[i:i + self.target_size]
                    if chunk_words:
                        chunks.append(" ".join(chunk_words))
                continue

            # Check if adding this sentence would exceed max_size
            if current_size + sentence_len > self.max_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                # Keep overlap sentences for context continuity
                if self.overlap_sentences > 0 and len(current_chunk) >= self.overlap_sentences:
                    current_chunk = current_chunk[-self.overlap_sentences:]
                    current_size = sum(len(s.split()) for s in current_chunk)
                else:
                    current_chunk = []
                    current_size = 0

            current_chunk.append(sentence)
            current_size += sentence_len

        # Don't forget the last chunk
        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return [c for c in chunks if len(c) > 50]  # Filter very small chunks


class QueryCache:
    """LRU cache for query embeddings to avoid redundant API calls"""

    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, Dict] = {}  # {query: {"embedding": [...], "timestamp": ...}}

    def _normalize_query(self, query: str) -> str:
        """Normalize query for consistent cache keys"""
        return " ".join(query.lower().split())

    def get(self, query: str) -> Optional[List[float]]:
        """Get cached embedding if valid"""
        key = self._normalize_query(query)
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry["timestamp"] < self.ttl_seconds:
                return entry["embedding"]
            else:
                # Expired
                del self.cache[key]
        return None

    def set(self, query: str, embedding: List[float]):
        """Store embedding in cache"""
        key = self._normalize_query(query)

        # Evict oldest entries if at capacity
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k]["timestamp"])
            del self.cache[oldest_key]

        self.cache[key] = {
            "embedding": embedding,
            "timestamp": time.time()
        }

    def clear(self):
        """Clear the cache"""
        self.cache.clear()

    def stats(self) -> Dict:
        """Get cache statistics"""
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds
        }


def highlight_query_terms(content: str, query: str, tag: str = "mark") -> str:
    """Highlight query terms in content for display"""
    # Extract meaningful words from query (skip common stop words)
    stop_words = {"the", "a", "an", "is", "are", "was", "were", "in", "on", "at", "to", "for",
                  "of", "and", "or", "but", "with", "what", "how", "why", "when", "where", "which"}
    query_words = [w for w in re.findall(r'\b\w+\b', query.lower()) if w not in stop_words and len(w) > 2]

    if not query_words:
        return content

    highlighted = content
    for word in query_words:
        # Case-insensitive replacement preserving original case
        pattern = re.compile(r'\b(' + re.escape(word) + r')\b', re.IGNORECASE)
        highlighted = pattern.sub(f'<{tag}>\\1</{tag}>', highlighted)

    return highlighted


class RAGEngine:
    """Simple RAG Engine using file-based storage and Ollama embeddings"""

    def __init__(self, chunking_strategy: str = "sentence"):
        self.documents: Dict[str, Document] = {}
        self.chunks: List[Dict] = []  # {id, doc_id, text, embedding}
        self.query_cache = QueryCache(max_size=100, ttl_seconds=3600)
        self.chunking_strategy = chunking_strategy
        self.sentence_chunker = SentenceChunker(target_size=400, max_size=600, overlap_sentences=1)
        self._load_index()

    def _load_index(self):
        """Load index from disk"""
        if os.path.exists(INDEX_FILE):
            try:
                with open(INDEX_FILE, "r") as f:
                    data = json.load(f)
                    for doc_data in data.get("documents", []):
                        doc = Document(**doc_data)
                        self.documents[doc.id] = doc
            except Exception as e:
                print(f"Error loading index: {e}")

        if os.path.exists(EMBEDDINGS_FILE):
            try:
                with open(EMBEDDINGS_FILE, "r") as f:
                    self.chunks = json.load(f)
            except Exception as e:
                print(f"Error loading embeddings: {e}")

    def _save_index(self):
        """Save index to disk"""
        try:
            with open(INDEX_FILE, "w") as f:
                json.dump({
                    "documents": [asdict(d) for d in self.documents.values()]
                }, f, indent=2)
        except Exception as e:
            print(f"Error saving index: {e}")

    def _save_embeddings(self):
        """Save embeddings to disk"""
        try:
            with open(EMBEDDINGS_FILE, "w") as f:
                json.dump(self.chunks, f)
        except Exception as e:
            print(f"Error saving embeddings: {e}")

    def _ollama_reachable(self) -> bool:
        """Quick check if Ollama is up — 2s timeout to avoid blocking."""
        try:
            with httpx.Client() as client:
                r = client.get(f"{OLLAMA_URL}/api/tags", timeout=2.0)
                return r.status_code == 200
        except Exception:
            return False

    def get_embedding_sync(self, text: str) -> Optional[List[float]]:
        """Get embedding from Ollama (sync version)"""
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{OLLAMA_URL}/api/embeddings",
                    json={"model": EMBEDDING_MODEL, "prompt": text[:8000]},
                    timeout=10.0
                )
                if response.status_code == 200:
                    return response.json().get("embedding")
                else:
                    print(f"Embedding error: {response.status_code}")
        except Exception as e:
            print(f"Embedding error: {e}")
        return None

    def normalize_text(self, text: str) -> str:
        """Normalize whitespace for consistent chunking."""
        return " ".join(text.split())

    def chunk_text(self, text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks using configured strategy"""
        if self.chunking_strategy == "sentence":
            return self.sentence_chunker.chunk(text)

        # Fallback to word-based chunking
        chunks = []
        words = text.split()

        if overlap >= chunk_size:
            overlap = max(0, chunk_size // 4)

        for i in range(0, len(words), chunk_size - overlap):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk.strip() and len(chunk) > 50:  # Skip very small chunks
                chunks.append(chunk)

        return chunks

    def extract_pdf_text(self, pdf_path: str) -> str:
        """Extract text from PDF"""
        if not PDF_SUPPORT:
            raise ImportError("PyPDF2 not installed")

        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
        return text

    def cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        a = np.array(a)
        b = np.array(b)
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        if denom == 0:
            return 0.0
        return float(np.dot(a, b) / denom)

    async def add_document(self, name: str, content: str, source: str = "", doc_type: str = "txt") -> Dict:
        """Add a document to the RAG system"""
        # Generate document ID
        doc_id = hashlib.md5(f"{name}{source}".encode()).hexdigest()[:12]

        # Check if already exists
        if doc_id in self.documents:
            return {"success": False, "error": "Document already exists", "id": doc_id}

        # Chunk the content
        normalized_content = self.normalize_text(content)
        text_chunks = self.chunk_text(normalized_content)
        if not text_chunks:
            return {"success": False, "error": "No content to index"}

        # Get embeddings and store
        if not self._ollama_reachable():
            return {"success": False, "error": "Ollama is offline — cannot generate embeddings"}

        added_chunks = 0
        existing_hashes = {c.get("hash") for c in self.chunks if c.get("hash")}
        for i, chunk in enumerate(text_chunks):
            chunk_hash = hashlib.md5(chunk.encode()).hexdigest()
            if chunk_hash in existing_hashes:
                continue
            embedding = self.get_embedding_sync(chunk)
            if embedding:
                self.chunks.append({
                    "id": f"{doc_id}_{i}",
                    "doc_id": doc_id,
                    "doc_name": name,
                    "text": chunk,
                    "embedding": embedding,
                    "hash": chunk_hash
                })
                added_chunks += 1
                existing_hashes.add(chunk_hash)

            # Progress indicator
            if (i + 1) % 10 == 0:
                print(f"  Processed {i + 1}/{len(text_chunks)} chunks...")

        if added_chunks == 0:
            return {"success": False, "error": "Failed to generate embeddings. Is Ollama running with nomic-embed-text?"}

        # Save document info
        doc = Document(
            id=doc_id,
            name=name,
            source=source,
            doc_type=doc_type,
            chunks=added_chunks,
            added=datetime.now().strftime("%Y-%m-%d %H:%M")
        )
        self.documents[doc_id] = doc

        # Save to disk
        self._save_index()
        self._save_embeddings()

        return {"success": True, "id": doc_id, "chunks": added_chunks}

    async def add_pdf(self, pdf_path: str, name: str = "") -> Dict:
        """Add a PDF document"""
        if not PDF_SUPPORT:
            return {"success": False, "error": "PyPDF2 not installed. Run: pip install PyPDF2"}

        if not name:
            name = os.path.basename(pdf_path)

        try:
            print(f"Extracting text from PDF: {name}")
            text = self.extract_pdf_text(pdf_path)
            if not text.strip():
                return {"success": False, "error": "No text could be extracted from PDF"}
            print(f"Extracted {len(text)} characters, indexing...")
            return await self.add_document(name, text, pdf_path, "pdf")
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def add_text_file(self, file_path: str, name: str = "") -> Dict:
        """Add a text file"""
        if not name:
            name = os.path.basename(file_path)

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            ext = os.path.splitext(file_path)[1].lower().lstrip(".") or "txt"
            return await self.add_document(name, text, file_path, ext)
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def query(self, question: str, n_results: int = 3, include_highlights: bool = True) -> Dict:
        """Query the RAG system with enhanced results"""
        start_time = time.time()

        if not self.chunks:
            return {
                "results": [],
                "query_time_ms": 0,
                "total_chunks": 0,
                "cache_hit": False
            }

        # Check cache first
        cache_hit = False
        query_embedding = self.query_cache.get(question)

        if query_embedding is None:
            # Get embedding for the question
            query_embedding = self.get_embedding_sync(question)
            if not query_embedding:
                return {
                    "results": [],
                    "query_time_ms": int((time.time() - start_time) * 1000),
                    "total_chunks": len(self.chunks),
                    "cache_hit": False,
                    "error": "Failed to generate query embedding"
                }
            # Store in cache
            self.query_cache.set(question, query_embedding)
        else:
            cache_hit = True

        # Calculate similarities
        results = []
        for chunk in self.chunks:
            if "embedding" in chunk and chunk["embedding"]:
                similarity = self.cosine_similarity(query_embedding, chunk["embedding"])
                score = round(similarity, 4)

                result = {
                    "content": chunk["text"],
                    "score": score,
                    "doc_id": chunk.get("doc_id", ""),
                    "doc_name": chunk.get("doc_name", "Unknown"),
                    "doc_type": self.documents.get(chunk.get("doc_id", ""), Document("", "", "", "unknown", 0, "")).doc_type
                }

                # Add highlighted content if requested
                if include_highlights:
                    result["highlighted_content"] = highlight_query_terms(chunk["text"], question)

                results.append(result)

        # Sort by similarity (highest score first)
        results.sort(key=lambda x: x["score"], reverse=True)

        query_time_ms = int((time.time() - start_time) * 1000)

        return {
            "results": results[:n_results],
            "query_time_ms": query_time_ms,
            "total_chunks": len(self.chunks),
            "cache_hit": cache_hit
        }

    async def query_simple(self, question: str, n_results: int = 3) -> List[Dict]:
        """Simplified query for backward compatibility - returns just the results list"""
        response = await self.query(question, n_results, include_highlights=False)
        # Convert to old format for compatibility
        return [
            {
                "content": r["content"],
                "metadata": {
                    "doc_id": r["doc_id"],
                    "doc_name": r["doc_name"]
                },
                "distance": 1 - r["score"]
            }
            for r in response.get("results", [])
        ]

    def get_documents(self) -> List[Dict]:
        """Get list of all indexed documents"""
        return [
            {
                "id": d.id,
                "name": d.name,
                "source": d.source,
                "type": d.doc_type,
                "chunks": d.chunks,
                "added": d.added
            }
            for d in self.documents.values()
        ]

    def delete_document(self, doc_id: str) -> Dict:
        """Delete a document from the RAG system"""
        if doc_id not in self.documents:
            return {"success": False, "error": "Document not found"}

        # Remove chunks
        self.chunks = [c for c in self.chunks if c.get("doc_id") != doc_id]

        # Remove from index
        del self.documents[doc_id]

        # Save changes
        self._save_index()
        self._save_embeddings()

        return {"success": True}

    def get_stats(self) -> Dict:
        """Get RAG system statistics"""
        return {
            "documents": len(self.documents),
            "chunks": len(self.chunks),
            "embedding_model": EMBEDDING_MODEL,
            "pdf_support": PDF_SUPPORT,
            "chunking_strategy": self.chunking_strategy,
            "query_cache": self.query_cache.stats()
        }

    def clear_cache(self):
        """Clear the query embedding cache"""
        self.query_cache.clear()


# Built-in mainframe knowledge
BUILTIN_KNOWLEDGE = """
# IBM z/OS ABEND Codes Reference

## System ABEND Codes (Sxxx)

### S0C1 - Operation Exception
Cause: Attempted to execute an invalid instruction
Common causes:
- Branch to invalid address or uninitialized storage
- Corrupted program code or overlay
- Missing module or CSECT
- Invalid entry point address
Fix: Check program logic, verify module linkage, check for storage overlays

### S0C4 - Protection Exception
Cause: Attempted to access storage not allocated to the program or protected
Common causes:
- Invalid pointer or address
- Array subscript out of bounds
- Working storage corruption
- Attempting to modify read-only storage
- Using CICS HANDLE ABEND improperly
Fix: Check array bounds, verify pointer initialization, review COBOL subscripts

### S0C7 - Data Exception
Cause: Invalid packed decimal data encountered during arithmetic operation
Common causes:
- Uninitialized packed decimal field (contains spaces or garbage)
- Non-numeric data moved to numeric field
- COBOL MOVE to wrong field type
- File record overlay corrupting numeric fields
- Missing or incorrect initialization of working storage
Fix: Initialize all numeric fields, check MOVE statements, use INITIALIZE verb, verify file layouts match

### S0CB - Division by Zero
Cause: Attempted to divide by zero
Fix: Add zero check before any division operation

### S222 - Job Cancelled by Operator
Cause: Job was cancelled by operator command or user request
- CANCEL command issued from console
- JES2/JES3 cancelled the job
- System timeout occurred

### S322 - CPU Time Exceeded
Cause: Job exceeded TIME parameter on JOB or EXEC statement
Fix: Increase TIME parameter, optimize program logic, check for infinite loops

### S806 - Module Not Found
Cause: LOAD, LINK, or XCTL failed because module not found in search path
Common causes:
- Module not in STEPLIB, JOBLIB, or link list
- Misspelled module name
- Module deleted or not linkedited
Fix: Check STEPLIB/JOBLIB DD statements, verify module exists in specified libraries

### S913 - RACF Authorization Failure
Cause: User not authorized to access the requested resource
Fix: Request appropriate RACF access from security administrator

### SB37 - Dataset Out of Space
Cause: Output dataset full, unable to obtain additional extents
Fix: Increase SPACE parameter, use larger primary/secondary allocations, enable SMS multivolume

### SD37 - No Space Available on Volume
Cause: Volume is full, no space for new extent
Fix: Use different volume, specify VOLUME count, clean up space on volume

### SE37 - Primary Space Exceeded
Cause: Primary allocation exhausted and secondary allocation failed
Fix: Increase SPACE parameter, check volume availability

## Common JCL Statements

### JOB Statement Parameters
//JOBNAME JOB (accounting),'programmer name',
//            CLASS=A,           Job class
//            MSGCLASS=X,        Output class for messages
//            MSGLEVEL=(1,1),    Print JCL and messages
//            NOTIFY=&SYSUID,    Notify user when complete
//            TIME=10,           CPU time limit in minutes
//            REGION=0M          Memory limit (0M = unlimited)

### EXEC Statement
//STEPNAME EXEC PGM=program     Execute a program
//STEPNAME EXEC PROC=procname   Execute a procedure

### DD Statement Types
//INPUT    DD DSN=MY.DATA,DISP=SHR              Read existing dataset
//OUTPUT   DD DSN=MY.NEW.DATA,                   Create new dataset
//            DISP=(NEW,CATLG,DELETE),
//            SPACE=(CYL,(10,5),RLSE),
//            DCB=(RECFM=FB,LRECL=80,BLKSIZE=27920)
//SYSOUT   DD SYSOUT=*                           Print output
//SYSIN    DD *                                   Inline data
data here
/*

### DISP Parameter Values
- Status: NEW, OLD, SHR, MOD
- Normal termination: KEEP, DELETE, CATLG, UNCATLG, PASS
- Abnormal termination: KEEP, DELETE, CATLG, UNCATLG

### SPACE Parameter
SPACE=(unit,(primary,secondary,directory),RLSE)
- Units: TRK (tracks), CYL (cylinders), blksize
- RLSE releases unused space

### DCB Parameters
- RECFM: F (fixed), FB (fixed blocked), V (variable), VB (variable blocked)
- LRECL: Logical record length
- BLKSIZE: Block size (should be multiple of LRECL for FB)

## TSO/ISPF Navigation

### ISPF Primary Option Menu
Option 1 - View: Browse datasets (read-only)
Option 2 - Edit: Edit datasets
Option 3 - Utilities: Dataset utilities (copy, rename, delete, etc.)
Option 4 - Foreground: Run programs interactively
Option 5 - Batch: Submit batch jobs
Option 6 - Command: TSO command processor
Option SD - SDSF: Job output viewer
=X - Exit ISPF

### ISPF Edit Primary Commands
SAVE - Save the dataset
CANCEL - Exit without saving
FIND string - Find text (F string)
CHANGE old new - Replace text (C old new ALL)
COPY - Copy from another dataset
SUBMIT - Submit JCL for execution

### ISPF Edit Line Commands
I - Insert line
D - Delete line
C - Copy line
M - Move line
R - Repeat line
A - After (target for copy/move)
B - Before (target for copy/move)

### Standard PF Keys
PF1 - Help
PF2 - Split screen
PF3 - End/Return
PF7 - Scroll up/backward
PF8 - Scroll down/forward
PF10 - Scroll left
PF11 - Scroll right
PF12 - Retrieve last command

## COBOL Quick Reference

### Program Structure
IDENTIFICATION DIVISION.
PROGRAM-ID. program-name.

ENVIRONMENT DIVISION.
INPUT-OUTPUT SECTION.
FILE-CONTROL.
    SELECT file-name ASSIGN TO ddname.

DATA DIVISION.
FILE SECTION.
FD file-name.
01 record-name.
   05 field-name PIC X(10).

WORKING-STORAGE SECTION.
01 WS-VARIABLES.
   05 WS-COUNTER    PIC 9(4) VALUE 0.
   05 WS-NAME       PIC X(30).
   05 WS-AMOUNT     PIC S9(7)V99 COMP-3.

PROCEDURE DIVISION.
    PERFORM initialization
    PERFORM main-process UNTIL end-of-file
    PERFORM cleanup
    STOP RUN.

### Data Types
PIC 9(n) - Unsigned numeric display
PIC S9(n) - Signed numeric display
PIC X(n) - Alphanumeric
PIC S9(n) COMP-3 - Packed decimal (efficient storage)
PIC S9(n) COMP - Binary (computational)
PIC S9(n)V99 - Implied decimal (2 places)

### Common Verbs
MOVE source TO destination
ADD a TO b GIVING c
SUBTRACT a FROM b
MULTIPLY a BY b GIVING c
DIVIDE a INTO b GIVING c REMAINDER r
COMPUTE result = expression
IF condition THEN ... ELSE ... END-IF
EVALUATE TRUE WHEN condition ... END-EVALUATE
PERFORM paragraph
PERFORM paragraph UNTIL condition
PERFORM paragraph VARYING counter FROM 1 BY 1 UNTIL counter > 10
READ file-name INTO ws-record AT END SET end-of-file TO TRUE
WRITE record-name FROM ws-record
OPEN INPUT file-name / OUTPUT file-name
CLOSE file-name
CALL 'program' USING param1 param2
GOBACK
STOP RUN

## CICS Commands

### Terminal I/O
EXEC CICS SEND TEXT FROM(data) LENGTH(len) END-EXEC
EXEC CICS RECEIVE INTO(data) LENGTH(len) END-EXEC
EXEC CICS SEND MAP(mapname) MAPSET(mapsetname) END-EXEC
EXEC CICS RECEIVE MAP(mapname) MAPSET(mapsetname) INTO(data) END-EXEC

### File Operations
EXEC CICS READ FILE(filename) INTO(data) RIDFLD(key) END-EXEC
EXEC CICS WRITE FILE(filename) FROM(data) RIDFLD(key) END-EXEC
EXEC CICS REWRITE FILE(filename) FROM(data) END-EXEC
EXEC CICS DELETE FILE(filename) RIDFLD(key) END-EXEC

### Program Control
EXEC CICS LINK PROGRAM(progname) COMMAREA(data) END-EXEC
EXEC CICS XCTL PROGRAM(progname) COMMAREA(data) END-EXEC
EXEC CICS RETURN END-EXEC
EXEC CICS RETURN TRANSID(trans) END-EXEC

### Error Handling
EXEC CICS HANDLE CONDITION ERROR(label) END-EXEC
EXEC CICS HANDLE ABEND LABEL(label) END-EXEC

## DB2 SQL Basics

### COBOL Declaration
EXEC SQL
    SELECT column1, column2
    INTO :ws-var1, :ws-var2
    FROM table
    WHERE key = :ws-key
END-EXEC

### Common Operations
SELECT, INSERT, UPDATE, DELETE
DECLARE CURSOR, OPEN CURSOR, FETCH, CLOSE CURSOR
COMMIT, ROLLBACK

### SQLCODE Values
0 - Successful
100 - Not found
-803 - Duplicate key
-811 - More than one row returned
-904 - Resource unavailable
-911 - Timeout/deadlock
"""


# Global RAG engine instance
rag_engine = None


def get_rag_engine() -> RAGEngine:
    """Get or create RAG engine instance"""
    global rag_engine
    if rag_engine is None:
        rag_engine = RAGEngine()
    return rag_engine


async def initialize_builtin_knowledge():
    """Add built-in mainframe knowledge to RAG"""
    engine = get_rag_engine()

    # Check if already added
    for doc in engine.documents.values():
        if doc.name == "Mainframe Quick Reference":
            return {"success": True, "message": "Already initialized"}

    print("Loading built-in mainframe knowledge...")
    result = await engine.add_document(
        name="Mainframe Quick Reference",
        content=BUILTIN_KNOWLEDGE,
        source="builtin",
        doc_type="builtin"
    )

    return result
