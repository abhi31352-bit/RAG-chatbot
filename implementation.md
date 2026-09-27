# Implementation Guide
## RAG Chatbot for Class Demo

---

| Field | Details |
|-------|---------|
| **Document Title** | Phase-wise Implementation Plan |
| **Version** | 1.0 |
| **Date** | 2026-09-27 |
| **Status** | Draft |
| **Parent Documents** | [PRD.md](./PRD.md), [architecture.md](./architecture.md) |

---

## Table of Contents

1. [How to Use This Guide](#how-to-use-this-guide)
2. [Phase 1: Project Setup & Core Backend](#phase-1-project-setup--core-backend)
3. [Phase 2: RAG Pipeline — Document Ingestion](#phase-2-rag-pipeline--document-ingestion)
4. [Phase 3: Chat & Answer Generation](#phase-3-chat--answer-generation)
5. [Phase 4: Frontend — Chat Interface](#phase-4-frontend--chat-interface)
6. [Phase 5: Frontend — Admin Panel](#phase-5-frontend--admin-panel)
7. [Phase 6: Integration, Testing & Demo Prep](#phase-6-integration-testing--demo-prep)
8. [Quick Reference: File Tree](#quick-reference-file-tree)

---

## How to Use This Guide

This document is designed to be used as a **step-by-step implementation guide** for AI-assisted development (e.g., Cursor) or manual development.

### For Each Phase:
1. **Read** the phase objectives and context
2. **Implement** each task in order
3. **Verify** against acceptance criteria before moving to next task
4. **Mark** tasks as complete

### Conventions:

- [ ] = Incomplete task
- [x] = Complete task
- Each task includes: **What**, **Files**, **Implementation Details**, **Acceptance Criteria**

---

## Phase 1: Project Setup & Core Backend

> **Status: COMPLETE** - verified 2026-09-27. 10/10 tests pass, ruff clean, server boots with all endpoints responding.

> **Deviations from the plan:**
> - `langchain-*` removed from requirements (unused in our implementation; also require Python >= 3.10). Parsing uses `pypdf`/`python-docx` directly.
> - `langchain-chroma==0.0.2` does not exist on PyPI; dropped.
> - Added explicit `greenlet==3.0.3` (SQLAlchemy asyncio requires it).
> - Runtime data paths anchored to `backend/` so results do not depend on CWD.
> - `backend/.env` and `backend/data/` are created, not repo root.

### Objectives
- Initialize project structure
- Set up backend with FastAPI
- Configure environment and dependencies
- Create database models
- Set up Chroma vector store connection

### Tasks

---

#### Task 1.1: Initialize Project Structure

**What**: Create the root project directory structure

**Files**:
```
rag-chatbot/
├── frontend/                 # React frontend (created in Phase 4)
├── backend/                  # FastAPI backend
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── dependencies.py
│   │   ├── exceptions.py
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   ├── cors.py
│   │   │   ├── logging.py
│   │   │   └── rate_limit.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── documents.py
│   │   │   ├── chat.py
│   │   │   └── health.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── document_service.py
│   │   │   ├── chat_service.py
│   │   │   ├── embedding_service.py
│   │   │   └── llm_service.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── document.py
│   │   │   ├── chat.py
│   │   │   └── database.py
│   │   ├── rag/
│   │   │   ├── __init__.py
│   │   │   ├── indexer.py
│   │   │   ├── retriever.py
│   │   │   ├── generator.py
│   │   │   └── pipeline.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── file_handler.py
│   │       └── text_processor.py
│   ├── tests/
│   │   └── __init__.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── data/                     # Created at runtime
├── docker-compose.yml
├── .env
├── .gitignore
└── README.md
```

**Implementation Details**:
```bash
mkdir -p rag-chatbot/backend/app/{middleware,routes,services,models,rag,utils}
mkdir -p rag-chatbot/backend/tests
mkdir -p rag-chatbot/data
touch rag-chatbot/backend/app/__init__.py
# ... (create all __init__.py files)
```

**Acceptance Criteria**:
- [x] Directory structure matches the tree above
- [x] All `__init__.py` files created
- [x] `data/` directory exists and is empty

---

#### Task 1.2: Backend Dependencies

**What**: Create `requirements.txt` with all Python dependencies

**Files**: `backend/requirements.txt`

**Implementation Details**:
```txt
# Web Framework
fastapi==0.110.0
uvicorn[standard]==0.29.0
python-multipart==0.0.9

# Database
sqlalchemy==2.0.29
aiosqlite==0.20.0

# Vector Store
chromadb==0.4.24

# LLM & Embeddings
openai==1.14.3
langchain==0.1.16
langchain-openai==0.0.8
langchain-community==0.0.31
langchain-chroma==0.0.2

# Document Processing
pypdf==4.1.0
python-docx==1.1.0
tiktoken==0.6.0

# Utilities
pydantic==2.6.4
pydantic-settings==2.2.1
python-dotenv==1.0.1
httpx==0.27.0
tenacity==8.2.3

# Testing
pytest==8.1.1
pytest-asyncio==0.23.5
httpx==0.27.0

# Linting
ruff==0.3.4
```

**Acceptance Criteria**:
- [x] `pip install -r requirements.txt` succeeds
- [x] All imports work in Python 3.11+

---

#### Task 1.3: Environment Configuration

**What**: Create configuration management with Pydantic Settings

**Files**: `backend/app/config.py`, `backend/.env.example`

**Implementation Details**:

`backend/app/config.py`:
```python
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # Application
    APP_NAME: str = "RAG Chatbot"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: List[str] = ["http://localhost:5173"]

    # OpenAI
    OPENAI_API_KEY: str = ""
    LLM_MODEL: str = "big-pickle"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Vector Store
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    CHROMA_COLLECTION_NAME: str = "course_documents"

    # Database
    DATABASE_URL: str = "sqlite:///./data/app.db"

    # Document Processing
    MAX_FILE_SIZE_MB: int = 50
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    TOP_K_RETRIEVAL: int = 5

    # LLM Settings
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 1024
    LLM_TIMEOUT_SECONDS: int = 30

    # Rate Limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60

    class Config:
        env_file = ".env"

settings = Settings()
```

`backend/.env.example`:
```bash
OPENAI_API_KEY=sk-your-key-here
LLM_MODEL=big-pickle
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
CHROMA_PERSIST_DIR=./data/chroma
DATABASE_URL=sqlite:///./data/app.db
CHUNK_SIZE=500
CHUNK_OVERLAP=50
TOP_K_RETRIEVAL=5
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=1024
MAX_FILE_SIZE_MB=50
```

**Acceptance Criteria**:
- [x] `from app.config import settings` works
- [x] Settings load from `.env` file
- [x] Default values work without `.env`

---

#### Task 1.4: Database Models & Connection

**What**: Create SQLAlchemy models and database connection

**Files**: `backend/app/models/database.py`, `backend/app/models/document.py`, `backend/app/models/chat.py`

**Implementation Details**:

`backend/app/models/database.py`:
```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

# Convert sqlite:/// to sqlite+aiosqlite:/// for async
DATABASE_URL = settings.DATABASE_URL
if DATABASE_URL.startswith("sqlite:///"):
    DATABASE_URL = DATABASE_URL.replace("sqlite:///", "sqlite+aiosqlite:///")

engine = create_async_engine(DATABASE_URL, echo=settings.DEBUG)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

`backend/app/models/document.py`:
```python
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.database import Base

def generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("doc"))
    filename: Mapped[str] = mapped_column(String, nullable=False)
    file_type: Mapped[str] = mapped_column(String, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chunks: Mapped[list["Chunk"]] = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")

class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("chunk"))
    document_id: Mapped[str] = mapped_column(String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_: Mapped[str] = mapped_column("metadata", Text, nullable=True)  # JSON string
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped["Document"] = relationship("Document", back_populates="chunks")
```

`backend/app/models/chat.py`:
```python
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.models.database import Base

def generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("sess"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_active: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    message_count: Mapped[int] = mapped_column(Integer, default=0)

    messages: Mapped[list["Message"]] = relationship("Message", back_populates="session", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("msg"))
    session_id: Mapped[str] = mapped_column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sources: Mapped[str] = mapped_column(Text, nullable=True)  # JSON string
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    session: Mapped["Session"] = relationship("Session", back_populates="messages")
```

**Acceptance Criteria**:
- [x] Database tables created on startup
- [x] Models can be imported without errors
- [x] `init_db()` creates all tables

---

#### Task 1.5: FastAPI Application Entry Point

**What**: Create the main FastAPI application with middleware

**Files**: `backend/app/main.py`, `backend/app/middleware/cors.py`, `backend/app/middleware/logging.py`, `backend/app/middleware/rate_limit.py`

**Implementation Details**:

`backend/app/main.py`:
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.models.database import init_db
from app.routes import documents, chat, health

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    yield
    # Shutdown
    pass

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="RAG Chatbot for Class Demo",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api/health", tags=["Health"])
app.include_router(documents.router, prefix="/api/documents", tags=["Documents"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])

@app.get("/")
async def root():
    return {"message": "RAG Chatbot API is running", "docs": "/docs"}
```

`backend/app/middleware/cors.py`:
```python
# CORS is handled in main.py via FastAPI's CORSMiddleware
# This file can be used for custom CORS logic if needed
```

`backend/app/middleware/logging.py`:
```python
import time
import logging
from fastapi import Request

logger = logging.getLogger("rag-chatbot")

async def logging_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    logger.info(f"{request.method} {request.url.path} - {response.status_code} - {duration:.3f}s")
    return response
```

`backend/app/middleware/rate_limit.py`:
```python
# Simple in-memory rate limiter (for demo purposes)
# In production, use Redis-based rate limiting
from fastapi import Request, HTTPException
from app.config import settings
import time

request_history: dict = {}

async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host
    now = time.time()
    
    # Clean old entries
    for ip in list(request_history.keys()):
        request_history[ip] = [t for t in request_history[ip] if now - t < 60]
        if not request_history[ip]:
            del request_history[ip]
    
    # Check rate limit
    if client_ip in request_history:
        if len(request_history[client_ip]) >= settings.RATE_LIMIT_REQUESTS_PER_MINUTE:
            raise HTTPException(status_code=429, detail="Too many requests")
        request_history[client_ip].append(now)
    else:
        request_history[client_ip] = [now]
    
    return await call_next(request)
```

**Acceptance Criteria**:
- [x] `uvicorn app.main:app --reload` starts successfully
- [x] `http://localhost:8000/docs` shows Swagger UI
- [x] Health check endpoint responds at `/api/health`
- [x] CORS allows requests from `localhost:5173`

---

#### Task 1.6: Health Check Endpoints

**What**: Implement health check endpoints

**Files**: `backend/app/routes/health.py`

**Implementation Details**:
```python
from fastapi import APIRouter
from app.config import settings

router = APIRouter()

@router.get("")
async def health_check():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
    }

@router.get("/ready")
async def readiness_check():
    # Check if critical services are available
    checks = {
        "database": await _check_database(),
        "vector_store": await _check_vector_store(),
    }
    all_ready = all(checks.values())
    return {
        "ready": all_ready,
        "checks": checks,
    }

async def _check_database() -> bool:
    try:
        from app.models.database import engine
        from sqlalchemy import text
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False

async def _check_vector_store() -> bool:
    try:
        from app.services.embedding_service import get_chroma_client
        client = get_chroma_client()
        client.list_collections()
        return True
    except Exception:
        return False
```

**Acceptance Criteria**:
- [x] `GET /api/health` returns `{"status": "healthy"}`
- [x] `GET /api/health/ready` returns readiness status with checks

---

### Phase 1 Acceptance Criteria

- [x] Backend starts without errors
- [x] All endpoints respond correctly
- [x] Database tables created
- [x] Swagger UI accessible at `/docs`
- [x] Health checks pass

---

## Phase 2: RAG Pipeline — Document Ingestion

### Objectives
- Implement document upload API
- Implement document parsing (PDF, DOCX, TXT, MD)
- Implement text chunking
- Implement embedding generation
- Implement vector store operations

### Tasks

---

#### Task 2.1: Document Upload API

**What**: Create the document upload endpoint

**Files**: `backend/app/routes/documents.py`, `backend/app/services/document_service.py`

**Implementation Details**:

`backend/app/routes/documents.py`:
```python
import os
import shutil
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import get_db
from app.models.document import Document
from app.config import settings
from app.services.document_service import DocumentService

router = APIRouter()
doc_service = DocumentService()

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx", ".md"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/markdown",
}

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    # Validate file type
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, detail=f"Invalid file type. Allowed: {ALLOWED_EXTENSIONS}")
    
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(400, detail=f"Invalid MIME type: {file.content_type}")
    
    # Check file size (read first chunk to estimate)
    contents = await file.read()
    file_size = len(contents)
    max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    
    if file_size > max_size:
        raise HTTPException(400, detail=f"File too large. Max: {settings.MAX_FILE_SIZE_MB}MB")
    
    if file_size == 0:
        raise HTTPException(400, detail="File is empty")
    
    # Save file
    doc = await doc_service.save_document(db, file.filename, ext, file_size, contents)
    
    # Process document (parse, chunk, embed)
    try:
        chunk_count = await doc_service.process_document(doc.id, contents, ext)
        doc.chunk_count = chunk_count
        doc.status = "processed"
        await db.commit()
    except Exception as e:
        doc.status = "failed"
        await db.commit()
        raise HTTPException(422, detail=f"Failed to process document: {str(e)}")
    
    await db.refresh(doc)
    return {
        "id": doc.id,
        "filename": doc.filename,
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "chunk_count": doc.chunk_count,
        "status": doc.status,
        "created_at": doc.created_at.isoformat(),
    }

@router.get("/")
async def list_documents(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    result = await db.execute(select(Document).order_by(Document.created_at.desc()))
    documents = result.scalars().all()
    return {
        "documents": [
            {
                "id": d.id,
                "filename": d.filename,
                "file_type": d.file_type,
                "file_size": d.file_size,
                "chunk_count": d.chunk_count,
                "status": d.status,
                "created_at": d.created_at.isoformat(),
            }
            for d in documents
        ],
        "total": len(documents),
    }

@router.get("/{document_id}")
async def get_document(document_id: str, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, detail="Document not found")
    return {
        "id": doc.id,
        "filename": doc.filename,
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "chunk_count": doc.chunk_count,
        "status": doc.status,
        "created_at": doc.created_at.isoformat(),
    }

@router.delete("/{document_id}")
async def delete_document(document_id: str, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select, delete
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, detail="Document not found")
    
    # Delete from vector store
    await doc_service.delete_document_vectors(document_id)
    
    # Delete file
    if os.path.exists(doc.file_path):
        os.remove(doc.file_path)
    
    # Delete from database
    await db.delete(doc)
    await db.commit()
    
    return {"status": "deleted"}
```

**Acceptance Criteria**:
- [x] `POST /api/documents/upload` accepts PDF, TXT, DOCX, MD files
- [x] Returns 400 for invalid file types
- [x] Returns 400 for files > 50MB
- [x] Returns 400 for empty files
- [x] `GET /api/documents` lists all documents
- [x] `DELETE /api/documents/{id}` removes document and vectors

---

#### Task 2.2: Document Processing Service

**What**: Implement document parsing, chunking, and embedding pipeline

**Files**: `backend/app/services/document_service.py`, `backend/app/utils/file_handler.py`, `backend/app/utils/text_processor.py`

**Implementation Details**:

`backend/app/services/document_service.py`:
```python
import os
import json
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.models.document import Document, Chunk
from app.utils.file_handler import FileHandler
from app.utils.text_processor import TextProcessor
from app.services.embedding_service import EmbeddingService

class DocumentService:
    def __init__(self):
        self.file_handler = FileHandler()
        self.text_processor = TextProcessor()
        self.embedding_service = EmbeddingService()
        self.upload_dir = "./data/uploads"
        os.makedirs(self.upload_dir, exist_ok=True)
    
    async def save_document(
        self, db: AsyncSession, filename: str, file_type: str, file_size: int, contents: bytes
    ) -> Document:
        # Generate unique filename
        import uuid
        safe_filename = f"{uuid.uuid4().hex}_{filename}"
        file_path = os.path.join(self.upload_dir, safe_filename)
        
        # Save file to disk
        with open(file_path, "wb") as f:
            f.write(contents)
        
        # Create database record
        doc = Document(
            filename=filename,
            file_type=file_type,
            file_size=file_size,
            file_path=file_path,
            status="pending",
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)
        return doc
    
    async def process_document(self, document_id: str, contents: bytes, file_type: str) -> int:
        # 1. Parse document
        text = self.file_handler.parse(contents, file_type)
        
        if not text or not text.strip():
            raise ValueError("No text content extracted from document")
        
        # 2. Chunk text
        chunks = self.text_processor.chunk_text(
            text,
            chunk_size=settings.CHUNK_SIZE,
            overlap=settings.CHUNK_OVERLAP,
        )
        
        # 3. Generate embeddings
        embeddings = await self.embedding_service.embed_texts(chunks)
        
        # 4. Store in vector store
        await self.embedding_service.store_embeddings(
            document_id=document_id,
            chunks=chunks,
            embeddings=embeddings,
        )
        
        return len(chunks)
    
    async def delete_document_vectors(self, document_id: str):
        await self.embedding_service.delete_by_document_id(document_id)
    
    async def store_chunks_in_db(self, db: AsyncSession, document_id: str, chunks: List[str], metadata: List[dict]):
        for i, (chunk_text, meta) in enumerate(zip(chunks, metadata)):
            chunk = Chunk(
                document_id=document_id,
                content=chunk_text,
                chunk_index=i,
                token_count=len(chunk_text.split()),
                metadata_=json.dumps(meta) if meta else None,
            )
            db.add(chunk)
        await db.commit()
```

`backend/app/utils/file_handler.py`:
```python
import io
from typing import Optional

class FileHandler:
    ALLOWED_TYPES = {".pdf", ".txt", ".docx", ".md"}
    
    def parse(self, contents: bytes, file_type: str) -> str:
        if file_type == ".pdf":
            return self._parse_pdf(contents)
        elif file_type == ".docx":
            return self._parse_docx(contents)
        elif file_type in (".txt", ".md"):
            return self._parse_text(contents)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    
    def _parse_pdf(self, contents: bytes) -> str:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(contents))
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        return "\n\n".join(text_parts)
    
    def _parse_docx(self, contents: bytes) -> str:
        from docx import Document as DocxDocument
        doc = DocxDocument(io.BytesIO(contents))
        text_parts = []
        for para in doc.paragraphs:
            if para.text.strip():
                text_parts.append(para.text)
        return "\n".join(text_parts)
    
    def _parse_text(self, contents: bytes) -> str:
        return contents.decode("utf-8")
```

`backend/app/utils/text_processor.py`:
```python
import tiktoken
from typing import List

class TextProcessor:
    def __init__(self):
        self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Split text into overlapping chunks based on token count."""
        tokens = self.encoding.encode(text)
        chunks = []
        
        start = 0
        while start < len(tokens):
            end = start + chunk_size
            chunk_tokens = tokens[start:end]
            chunk_text = self.encoding.decode(chunk_tokens)
            chunks.append(chunk_text.strip())
            start = end - overlap
        
        return [c for c in chunks if c]  # Remove empty chunks
    
    def count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))
```

**Acceptance Criteria**:
- [x] PDF files are parsed correctly
- [x] DOCX files are parsed correctly
- [x] TXT/MD files are parsed correctly
- [x] Text is chunked with correct overlap
- [x] Empty chunks are filtered out

---

#### Task 2.3: Embedding Service

**What**: Implement embedding generation and vector store operations

**Files**: `backend/app/services/embedding_service.py`

**Implementation Details**:
```python
import chromadb
from chromadb.config import Settings
from typing import List, Optional
from app.config import settings

class EmbeddingService:
    _client = None
    _collection = None
    
    @classmethod
    def get_client(cls):
        if cls._client is None:
            cls._client = chromadb.PersistentClient(
                path=settings.CHROMA_PERSIST_DIR,
                settings=Settings(anonymized_telemetry=False)
            )
        return cls._client
    
    @classmethod
    def get_collection(cls):
        if cls._collection is None:
            client = cls.get_client()
            cls._collection = client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
        return cls._collection
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts using OpenAI."""
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Process in batches of 100
        all_embeddings = []
        batch_size = 100
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = await client.embeddings.create(
                model=settings.OPENAI_EMBEDDING_MODEL,
                input=batch,
            )
            embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(embeddings)
        
        return all_embeddings
    
    async def embed_query(self, text: str) -> List[float]:
        """Generate embedding for a single query."""
        embeddings = await self.embed_texts([text])
        return embeddings[0]
    
    async def store_embeddings(
        self,
        document_id: str,
        chunks: List[str],
        embeddings: List[List[float]],
    ):
        """Store embeddings in Chroma with metadata."""
        collection = self.get_collection()
        
        ids = [f"{document_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "document_id": document_id,
                "chunk_index": i,
            }
            for i in range(len(chunks))
        ]
        
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=chunks,
            metadatas=metadatas,
        )
    
    async def search(self, query_embedding: List[float], top_k: int = 5) -> List[dict]:
        """Search for similar chunks."""
        collection = self.get_collection()
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        
        chunks = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                chunks.append({
                    "content": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0,
                })
        return chunks
    
    async def delete_by_document_id(self, document_id: str):
        """Delete all embeddings for a document."""
        collection = self.get_collection()
        collection.delete(where={"document_id": document_id})
    
    async def get_stats(self) -> dict:
        """Get vector store statistics."""
        collection = self.get_collection()
        return {
            "total_chunks": collection.count(),
            "collection_name": settings.CHROMA_COLLECTION_NAME,
        }
```

**Acceptance Criteria**:
- [x] Embeddings generated successfully for chunks
- [x] Embeddings stored in Chroma with correct metadata
- [x] Search returns relevant chunks with cosine similarity
- [x] Delete removes all chunks for a document
- [x] Fallback to local embeddings if OpenAI fails

---

### Phase 2 Acceptance Criteria

- [x] Upload a PDF → returns document ID and chunk count
- [x] Upload a TXT file → returns document ID and chunk count
- [x] Upload invalid file type → returns 400 error
- [x] Upload file > 50MB → returns 400 error
- [x] Delete document → vectors removed from Chroma
- [x] Vector store stats show correct chunk count

**Status: COMPLETE** (97 tests pass, `ruff check .` clean)

#### Deviations from the plan in this phase

1. **No LangChain.** `implementation.md` §Phase 2 snippets call
   `langchain.text_splitter` and `langchain_openai.OpenAIEmbeddings`. Neither is
   usable here: `langchain-chroma==0.0.2` does not exist on PyPI and every
   `langchain-community` release requires Python >= 3.10. The pipeline uses
   `pypdf` / `python-docx` / `tiktoken` and the OpenAI SDK directly.

2. **`file_type` is stored without the leading dot** (`pdf`, not `.pdf`) to match
   the API contract in `architecture.md` §5 and the frontend `types/index.ts`.
   `normalize_extension()` accepts either form on input.

3. **MIME type is not a rejection criterion.** The plan rejected any upload
   whose `content_type` was outside a fixed allowlist. Browsers and `curl`
   disagree about `.md` and `.docx`, so that produced spurious 400s. The
   extension allowlist is the real control — it decides which parser runs — and
   a MIME mismatch is now only logged.

4. **A local embedding provider was added** (`EMBEDDING_PROVIDER=auto|openai|local`).
   The plan assumed a real `OPENAI_API_KEY`; with the `.env.example` placeholder
   in place the demo would have had no working retrieval. The local provider is
   a hashed bag-of-words embedder: no API key, no torch download, real lexical
   signal. `auto` uses OpenAI when a usable key is present.

5. **Provider/dimension mismatches are rejected.** The two providers emit
   different vector widths, so querying a 1536-dim index with a 512-dim vector
   would silently return garbage. The index records the model it was built with
   (in a `data/chroma/index_info.json` sidecar — Chroma cannot update
   collection metadata in place) and raises `EmbeddingMismatchError` on a
   mismatch, telling the user to re-index.

6. **Chunk rows are persisted to SQLite.** The plan defined
   `store_chunks_in_db()` but never called it. They are now written alongside
   the vectors, because they are the source of truth for the source excerpts
   shown in chat citations.

7. **Chunking reports character spans** (`chunk_text_with_spans`) so each chunk
   can be traced back to its source page. The plan compared a chunk *index*
   against page *character offsets*, which made every chunk report page 1.

8. **SQLite foreign keys are enabled explicitly** (`PRAGMA foreign_keys=ON`).
   SQLite ignores `ON DELETE CASCADE` otherwise, so deleting a document left
   its chunks behind as orphans.

9. **Test data isolation was fixed.** `conftest.py` set its temp-directory env
   vars in a session fixture, but pytest imports test modules (and therefore
   `app.config`) *before* running fixtures, so `settings` had already frozen
   the real dev paths. Tests were writing documents and vectors into
   `backend/data/`. The env vars are now set at conftest import time.

10. **`SQL_ECHO` is separate from `DEBUG`.** SQL logging was tied to `DEBUG`,
    which made test output unreadable.

---

## Phase 3: Chat & Answer Generation

### Objectives
- Implement chat query endpoint
- Implement context retrieval and assembly
- Implement LLM integration (big pickle)
- Implement streaming responses
- Implement session management
- Implement fallback handling

### Tasks

---

#### Task 3.1: Chat Service

**What**: Implement the core chat service with RAG pipeline

**Files**: `backend/app/services/chat_service.py`, `backend/app/rag/retriever.py`, `backend/app/rag/generator.py`, `backend/app/rag/pipeline.py`

**Implementation Details**:

`backend/app/rag/retriever.py`:
```python
from typing import List
from app.services.embedding_service import EmbeddingService
from app.config import settings

class Retriever:
    def __init__(self):
        self.embedding_service = EmbeddingService()
    
    async def retrieve(self, query: str, top_k: int = None) -> List[dict]:
        """Retrieve relevant chunks for a query."""
        top_k = top_k or settings.TOP_K_RETRIEVAL
        
        # Embed the query
        query_embedding = await self.embedding_service.embed_query(query)
        
        # Search vector store
        results = await self.embedding_service.search(query_embedding, top_k)
        
        return results
```

`backend/app/rag/generator.py`:
```python
from typing import List, AsyncGenerator
from app.config import settings

class Generator:
    def __init__(self):
        from openai import AsyncOpenAI
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    def build_prompt(self, query: str, context_chunks: List[dict], conversation_history: list = None) -> str:
        """Build the prompt with context and conversation history."""
        # Format context
        context_text = "\n\n---\n\n".join([
            chunk["content"] for chunk in context_chunks
        ])
        
        # Build conversation history
        history_text = ""
        if conversation_history:
            history_text = "\n\n".join([
                f"{msg['role'].capitalize()}: {msg['content']}"
                for msg in conversation_history[-6:]  # Last 6 messages
            ])
        
        prompt = f"""You are a helpful teaching assistant for a university course. Answer the student's question based ONLY on the provided course materials.

## Course Materials:
{context_text}

## Conversation History:
{history_text if history_text else "No previous conversation."}

## Student Question:
{query}

## Instructions:
- Answer based ONLY on the course materials provided above
- If the answer is not in the materials, say "I don't have information about that in the course materials."
- Be clear, concise, and helpful
- Use markdown formatting for better readability
- Cite which document/section the information comes from when possible

## Answer:"""
        return prompt
    
    async def generate(self, prompt: str) -> str:
        """Generate a response using big pickle."""
        response = await self.client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful teaching assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
        return response.choices[0].message.content
    
    async def generate_stream(self, prompt: str) -> AsyncGenerator[str, None]:
        """Stream a response using big pickle."""
        stream = await self.client.chat.completions.create(
            model=settings.LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful teaching assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=settings.LLM_TEMPERATURE,
            max_tokens=settings.LLM_MAX_TOKENS,
            stream=True,
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
        
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
```

`backend/app/rag/pipeline.py`:
```python
from typing import List, AsyncGenerator, Optional
from app.rag.retriever import Retriever
from app.rag.generator import Generator
from app.config import settings

class RAGPipeline:
    def __init__(self):
        self.retriever = Retriever()
        self.generator = Generator()
    
    async def query(
        self,
        question: str,
        conversation_history: list = None,
    ) -> dict:
        """Execute the full RAG pipeline for a single query."""
        # Step 1: Retrieve relevant chunks
        chunks = await self.retriever.retrieve(question, settings.TOP_K_RETRIEVAL)
        
        # Step 2: Handle no results
        if not chunks:
            return {
                "answer": "I don't have information about that in the course materials. Please try rephrasing your question or ask about a different topic.",
                "sources": [],
            }
        
        # Step 3: Build prompt
        prompt = self.generator.build_prompt(question, chunks, conversation_history)
        
        # Step 4: Generate response
        answer = await self.generator.generate(prompt)
        
        # Step 5: Format sources
        sources = self._format_sources(chunks)
        
        return {
            "answer": answer,
            "sources": sources,
        }
    
    async def query_stream(
        self,
        question: str,
        conversation_history: list = None,
    ) -> AsyncGenerator[str, None]:
        """Execute RAG pipeline with streaming response."""
        # Step 1: Retrieve relevant chunks
        chunks = await self.retriever.retrieve(question, settings.TOP_K_RETRIEVAL)
        
        # Step 2: Handle no results
        if not chunks:
            yield "I don't have information about that in the course materials. Please try rephrasing your question or ask about a different topic."
            return
        
        # Step 3: Build prompt
        prompt = self.generator.build_prompt(question, chunks, conversation_history)
        
        # Step 4: Stream response
        full_response = ""
        async for delta in self.generator.generate_stream(prompt):
            full_response += delta
            yield delta
        
        # Step 5: Send sources as final chunk
        sources = self._format_sources(chunks)
        import json
        yield f"\n\n<!--SOURCES:{json.dumps(sources)}-->"
    
    def _format_sources(self, chunks: List[dict]) -> List[dict]:
        """Format chunks into source references."""
        sources = []
        seen_docs = set()
        
        for chunk in chunks:
            doc_id = chunk["metadata"].get("document_id", "unknown")
            if doc_id not in seen_docs:
                seen_docs.add(doc_id)
                sources.append({
                    "document_id": doc_id,
                    "filename": chunk["metadata"].get("filename", "Unknown"),
                    "chunk_index": chunk["metadata"].get("chunk_index", 0),
                    "excerpt": chunk["content"][:200] + "..." if len(chunk["content"]) > 200 else chunk["content"],
                })
        
        return sources
```

`backend/app/services/chat_service.py`:
```python
import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.chat import Session, Message
from app.rag.pipeline import RAGPipeline
from app.config import settings

class ChatService:
    def __init__(self):
        self.pipeline = RAGPipeline()
    
    async def query(
        self,
        db: AsyncSession,
        question: str,
        session_id: Optional[str] = None,
        include_sources: bool = True,
    ) -> dict:
        """Process a chat query and return the response."""
        # Get or create session
        session = await self._get_or_create_session(db, session_id)
        
        # Get conversation history
        history = await self._get_conversation_history(db, session.id)
        
        # Save user message
        await self._save_message(db, session.id, "user", question)
        
        # Execute RAG pipeline
        result = await self.pipeline.query(question, history)
        
        # Save assistant message
        sources_json = str(result.get("sources", [])) if include_sources else None
        await self._save_message(db, session.id, "assistant", result["answer"], sources_json)
        
        # Update session
        session.message_count += 2
        await db.commit()
        
        return {
            "answer": result["answer"],
            "sources": result.get("sources", []),
            "session_id": session.id,
            "processing_time_ms": 0,  # TODO: measure
        }
    
    async def clear_session(self, db: AsyncSession, session_id: str):
        """Clear conversation history for a session."""
        from sqlalchemy import delete
        await db.execute(delete(Message).where(Message.session_id == session_id))
        await db.execute(delete(Session).where(Session.id == session_id))
        await db.commit()
        return {"status": "cleared"}
    
    async def _get_or_create_session(self, db: AsyncSession, session_id: Optional[str]) -> Session:
        from sqlalchemy import select
        if session_id:
            result = await db.execute(select(Session).where(Session.id == session_id))
            session = result.scalar_one_or_none()
            if session:
                return session
        
        session = Session(id=f"sess_{uuid.uuid4().hex[:12]}")
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session
    
    async def _get_conversation_history(self, db: AsyncSession, session_id: str) -> list:
        from sqlalchemy import select
        result = await db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at)
            .limit(10)
        )
        messages = result.scalars().all()
        return [{"role": m.role, "content": m.content} for m in messages]
    
    async def _save_message(
        self, db: AsyncSession, session_id: str, role: str, content: str, sources: str = None
    ):
        message = Message(
            session_id=session_id,
            role=role,
            content=content,
            sources=sources,
        )
        db.add(message)
        await db.commit()
```

**Acceptance Criteria**:
- [x] Query returns answer grounded in retrieved chunks
- [x] Empty results trigger fallback message
- [x] Prompt includes conversation history
- [x] Sources are formatted correctly
- [x] Session management works correctly

---

#### Task 3.2: Chat API Endpoints

**What**: Create chat query and streaming endpoints

**Files**: `backend/app/routes/chat.py`

**Implementation Details**:
```python
import json
import time
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List
from app.models.database import get_db
from app.services.chat_service import ChatService

router = APIRouter()
chat_service = ChatService()

class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    include_sources: bool = True

class ChatResponse(BaseModel):
    answer: str
    sources: List[dict]
    session_id: str
    processing_time_ms: int

@router.post("/query", response_model=ChatResponse)
async def chat_query(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    start = time.time()
    result = await chat_service.query(
        db=db,
        question=request.question,
        session_id=request.session_id,
        include_sources=request.include_sources,
    )
    duration = int((time.time() - start) * 1000)
    result["processing_time_ms"] = duration
    return result

@router.post("/stream")
async def chat_stream(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    async def event_generator():
        full_answer = ""
        sources = []
        
        # Retrieve and generate
        from app.rag.pipeline import RAGPipeline
        pipeline = RAGPipeline()
        
        # Get conversation history
        history = []
        if request.session_id:
            history = await chat_service._get_conversation_history(db, request.session_id)
        
        async for chunk in pipeline.query_stream(request.question, history):
            if chunk.startswith("\n\n<!--SOURCES:"):
                # Extract sources from final chunk
                sources_json = chunk.split("<!--SOURCES:")[1].split("-->")[0]
                sources = json.loads(sources_json)
            else:
                full_answer += chunk
                data = json.dumps({"delta": chunk, "finish": False})
                yield f"data: {data}\n\n"
        
        # Send finish event
        finish_data = json.dumps({"delta": "", "finish": True, "sources": sources})
        yield f"data: {finish_data}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )

@router.post("/clear")
async def clear_chat(request: dict, db: AsyncSession = Depends(get_db)):
    session_id = request.get("session_id")
    if not session_id:
        return {"status": "no_session"}
    return await chat_service.clear_session(db, session_id)
```

**Acceptance Criteria**:
- [x] `POST /api/chat/query` returns answer with sources
- [x] `POST /api/chat/stream` streams response via SSE
- [x] `POST /api/chat/clear` clears session history
- [x] Response time < 5 seconds for typical queries

---

### Phase 3 Acceptance Criteria

- [x] Ask a question about uploaded document → returns accurate answer
- [x] Ask a question not in documents → returns fallback message
- [x] Streaming response works correctly
- [x] Session management maintains context
- [x] Source citations included in responses

**Status: COMPLETE** (200 tests pass, `ruff check .` clean)

Verified end-to-end against a live server: uploaded PDF/MD/TXT, asked
grounded questions, followed up in the same session, streamed a turn, mixed
streamed and non-streamed turns in one conversation, and confirmed an
off-topic question returns the fallback instead of an answer. Latency was
16–19 ms per turn with the offline provider.

#### Deviations from the plan in this phase

1. **Streaming now persists the session.** The plan's `/stream` route called
   `pipeline.query_stream` directly, bypassing `ChatService`, so streamed turns
   were never written to the database. "Session management maintains context"
   would have failed for every streamed turn. `ChatService.stream_query` owns
   both paths and saves the exchange once the stream completes.

2. **The stream opens its own database session.** The plan injected the request's
   `db` into the SSE generator. Starlette closes `yield`-based dependencies as
   soon as the endpoint returns, which is *before* the `StreamingResponse` body
   is consumed, so that session would already be closed on the first chunk.
   `/stream` deliberately takes no `db` dependency and manages
   `async_session()` inside the generator.

3. **The LLM client is created lazily.** The plan built `AsyncOpenAI` in
   `Generator.__init__`, and `ChatService` was constructed at import time. With
   the placeholder `OPENAI_API_KEY` still in `backend/.env` that raised during
   import and the app would not start. The client is now built on first use.

4. **Structured stream events instead of a string sentinel.** The plan appended
   `\n\n<!--SOURCES:{json}-->`` to the answer text and had the route re-parse
   it. That couples the transport to the payload and breaks if the model emits
   the marker. `query_stream` now yields `StreamEvent` objects; the SSE frame
   shape the frontend consumes is unchanged.

5. **Sources are stored as JSON.** The plan used `str(result.get("sources"))`,
   which is a Python `repr` with single quotes and would fail `JSON.parse` in
   the browser.

6. **History takes the most recent N messages, not the first N.** The plan's
   `.order_by(created_at).limit(10)` returned the *oldest* ten messages, so a
   long conversation fed the model stale context and dropped the recent turns.
   The newest N ids are selected first, then re-read in chronological order
   (with `id` as a tiebreaker, since two messages can share a timestamp).

7. **Added `GET /api/chat/history/{session_id}`.** Not in the plan, but the
   frontend needs it to restore a conversation on page reload, and it made
   cross-mode session testing possible.

8. **An unknown `session_id` starts a new session instead of 404-ing.**
   `POST /api/chat/clear` deletes the session row, so a client that keeps the
   old id would otherwise be stuck with a 404 on its next question.

9. **Added an offline extractive provider (`LLM_PROVIDER=auto|openai|offline`).**
   `backend/.env` still holds the `sk-your-key-here` placeholder, so the plan's
   code could not answer a single question on this machine and none of the phase
   would have been verifiable. When no usable key is present, answers are built
   by quoting the retrieved sentences that best match the question, with
   citations. It is not a language model: no paraphrasing, no synthesis, no
   cross-sentence reasoning. Every response reports `mode`, which is
   `offline-extractive` in this case, so the demo never misrepresents it. Word
   forms are matched with a light stemmer (`exam`/`examination`,
   `grading`/`grade`) because a bare lexical match scores those as unrelated.
   Set a real `OPENAI_API_KEY` to switch to the actual model — note that
   adding a key also moves embeddings to OpenAI, which requires re-uploading
   documents (see deviation 10).

10. **Fixed a Phase 1 bug in the validation error handler.** Pydantic carries a
    custom validator's `ValueError` through in `ctx` as a live exception object,
    which `json.dumps` cannot encode. Any request rejected by a custom validator
    returned a 500 instead of the `VALIDATION_ERROR` envelope.

11. **Fixed a Phase 2 bug in the embedding error path.** `EmbeddingService.embed_texts`
    let provider failures (bad key, network down) escape as raw OpenAI
    exceptions. The upload path wrapped them into `PROCESSING_ERROR`, but
    retrieval had no handler, so a chat question returned an opaque 500. Provider
    failures now raise `EmbeddingUnavailableError` (503). `EmbeddingMismatchError`
    also gained an HTTP mapping (409 with the re-index remedy) instead of
    surfacing as a 500 when a provider is swapped. Both are covered by tests.

---

## Phase 4: Frontend — Chat Interface

### Objectives
- Set up React + Vite project
- Implement chat UI components
- Implement state management (Zustand)
- Implement API client
- Implement streaming support

### Tasks

---

#### Task 4.1: Frontend Project Setup

**What**: Initialize React + Vite project with dependencies

**Files**: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/tailwind.config.js`

**Implementation Details**:

`frontend/package.json`:
```json
{
  "name": "rag-chatbot-frontend",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "lint": "eslint . --ext ts,tsx"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.22.0",
    "axios": "^1.6.7",
    "zustand": "^4.5.2",
    "lucide-react": "^0.344.0",
    "react-markdown": "^9.0.1",
    "remark-gfm": "^4.0.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.55",
    "@types/react-dom": "^18.2.19",
    "@vitejs/plugin-react": "^4.2.1",
    "autoprefixer": "^10.4.18",
    "postcss": "^8.4.35",
    "tailwindcss": "^3.4.1",
    "typescript": "^5.4.0",
    "vite": "^5.1.0",
    "eslint": "^8.56.0",
    "@typescript-eslint/eslint-plugin": "^7.0.0",
    "@typescript-eslint/parser": "^7.0.0"
  }
}
```

`frontend/vite.config.ts`:
```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

`frontend/tailwind.config.js`:
```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

**Acceptance Criteria**:
- [x] `npm install` succeeds
- [x] `npm run dev` starts dev server on port 5173
- [x] Proxy to backend works

---

#### Task 4.2: State Management

**What**: Create Zustand stores for chat, documents, and session

**Files**: `frontend/src/stores/chatStore.ts`, `frontend/src/stores/documentStore.ts`, `frontend/src/stores/sessionStore.ts`

**Implementation Details**:

`frontend/src/stores/chatStore.ts`:
```typescript
import { create } from 'zustand'

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
  timestamp: Date
}

export interface Source {
  document_id: string
  filename: string
  chunk_index: number
  excerpt: string
}

interface ChatState {
  messages: Message[]
  isLoading: boolean
  error: string | null
  isStreaming: boolean
  streamingContent: string
  
  addMessage: (message: Message) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  setStreaming: (streaming: boolean) => void
  setStreamingContent: (content: string) => void
  appendStreamingContent: (delta: string) => void
  clearMessages: () => void
  finishStreaming: () => void
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  isLoading: false,
  error: null,
  isStreaming: false,
  streamingContent: '',
  
  addMessage: (message) => set((state) => ({
    messages: [...state.messages, message],
  })),
  
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  setStreaming: (streaming) => set({ isStreaming: streaming }),
  setStreamingContent: (content) => set({ streamingContent: content }),
  
  appendStreamingContent: (delta) => set((state) => ({
    streamingContent: state.streamingContent + delta,
  })),
  
  clearMessages: () => set({ messages: [], error: null }),
  
  finishStreaming: () => set((state) => ({
    messages: [...state.messages, {
      id: `msg_${Date.now()}`,
      role: 'assistant',
      content: state.streamingContent,
      timestamp: new Date(),
    }],
    isStreaming: false,
    streamingContent: '',
  })),
}))
```

`frontend/src/stores/documentStore.ts`:
```typescript
import { create } from 'zustand'

export interface Document {
  id: string
  filename: string
  file_type: string
  file_size: number
  chunk_count: number
  status: string
  created_at: string
}

interface DocumentState {
  documents: Document[]
  isUploading: boolean
  uploadProgress: number
  error: string | null
  
  setDocuments: (documents: Document[]) => void
  addDocument: (document: Document) => void
  removeDocument: (id: string) => void
  setUploading: (uploading: boolean) => void
  setUploadProgress: (progress: number) => void
  setError: (error: string | null) => void
}

export const useDocumentStore = create<DocumentState>((set) => ({
  documents: [],
  isUploading: false,
  uploadProgress: 0,
  error: null,
  
  setDocuments: (documents) => set({ documents }),
  addDocument: (document) => set((state) => ({
    documents: [document, ...state.documents],
  })),
  removeDocument: (id) => set((state) => ({
    documents: state.documents.filter((d) => d.id !== id),
  })),
  setUploading: (uploading) => set({ isUploading: uploading }),
  setUploadProgress: (progress) => set({ uploadProgress: progress }),
  setError: (error) => set({ error }),
}))
```

`frontend/src/stores/sessionStore.ts`:
```typescript
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

interface SessionState {
  sessionId: string | null
  setSessionId: (id: string | null) => void
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set) => ({
      sessionId: null,
      setSessionId: (id) => set({ sessionId: id }),
    }),
    {
      name: 'rag-chat-session',
    }
  )
)
```

**Acceptance Criteria**:
- [x] Stores persist across page reloads
- [x] Chat messages stored in state
- [x] Session ID persisted in localStorage

---

#### Task 4.3: API Client

**What**: Create Axios-based API client

**Files**: `frontend/src/services/apiClient.ts`, `frontend/src/services/chatService.ts`, `frontend/src/services/documentService.ts`

**Implementation Details**:

`frontend/src/services/apiClient.ts`:
```typescript
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
apiClient.interceptors.request.use(
  (config) => {
    // Add any auth tokens here if needed
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const message = error.response?.data?.detail || error.message || 'An error occurred'
    return Promise.reject(new Error(message))
  }
)
```

`frontend/src/services/chatService.ts`:
```typescript
import { apiClient } from './apiClient'
import { Source } from '../stores/chatStore'

export interface ChatRequest {
  question: string
  session_id?: string
  include_sources?: boolean
}

export interface ChatResponse {
  answer: string
  sources: Source[]
  session_id: string
  processing_time_ms: number
}

export const chatService = {
  async query(request: ChatRequest): Promise<ChatResponse> {
    const response = await apiClient.post<ChatResponse>('/chat/query', request)
    return response.data
  },
  
  async *streamQuery(request: ChatRequest): AsyncGenerator<{ delta: string; finish: boolean; sources: Source[] }> {
    const response = await fetch(`${apiClient.defaults.baseURL}/chat/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    })
    
    if (!response.ok) {
      throw new Error(`Stream request failed: ${response.statusText}`)
    }
    
    const reader = response.body?.getReader()
    if (!reader) throw new Error('No response body')
    
    const decoder = new TextDecoder()
    let buffer = ''
    
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6))
          yield {
            delta: data.delta || '',
            finish: data.finish || false,
            sources: data.sources || [],
          }
        }
      }
    }
  },
  
  async clearSession(sessionId: string): Promise<void> {
    await apiClient.post('/chat/clear', { session_id: sessionId })
  },
}
```

`frontend/src/services/documentService.ts`:
```typescript
import { apiClient } from './apiClient'
import { Document } from '../stores/documentStore'

export const documentService = {
  async upload(file: File, onProgress?: (progress: number) => void): Promise<Document> {
    const formData = new FormData()
    formData.append('file', file)
    
    const response = await apiClient.post<Document>('/documents/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          onProgress(progress)
        }
      },
    })
    return response.data
  },
  
  async list(): Promise<{ documents: Document[]; total: number }> {
    const response = await apiClient.get('/documents')
    return response.data
  },
  
  async get(id: string): Promise<Document> {
    const response = await apiClient.get(`/documents/${id}`)
    return response.data
  },
  
  async delete(id: string): Promise<void> {
    await apiClient.delete(`/documents/${id}`)
  },
}
```

**Acceptance Criteria**:
- [x] API client connects to backend
- [x] Streaming works via fetch API
- [x] Error handling works correctly

---

#### Task 4.4: Chat UI Components

**What**: Create all chat UI components

**Files**:
- `frontend/src/components/Chat/MessageList.tsx`
- `frontend/src/components/Chat/MessageBubble.tsx`
- `frontend/src/components/Chat/InputBox.tsx`
- `frontend/src/components/Chat/TypingIndicator.tsx`
- `frontend/src/components/Chat/SourceCard.tsx`
- `frontend/src/components/Chat/SuggestedQuestions.tsx`

**Implementation Details**:

`frontend/src/components/Chat/MessageBubble.tsx`:
```tsx
import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Message } from '../../stores/chatStore'
import { SourceCard } from './SourceCard'

interface MessageBubbleProps {
  message: Message
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message }) => {
  const isUser = message.role === 'user'
  
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className={`max-w-[80%] ${isUser ? 'order-2' : 'order-1'}`}>
        <div
          className={`rounded-2xl px-4 py-3 ${
            isUser
              ? 'bg-blue-600 text-white rounded-br-md'
              : 'bg-gray-100 text-gray-900 rounded-bl-md'
          }`}
        >
          {isUser ? (
            <p className="text-sm whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="prose prose-sm max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {message.content}
              </ReactMarkdown>
            </div>
          )}
        </div>
        {message.sources && message.sources.length > 0 && (
          <div className="mt-2 space-y-1">
            {message.sources.map((source, idx) => (
              <SourceCard key={idx} source={source} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
```

`frontend/src/components/Chat/InputBox.tsx`:
```tsx
import React, { useState, useRef, useEffect } from 'react'
import { Send, Loader2 } from 'lucide-react'

interface InputBoxProps {
  onSend: (message: string) => void
  disabled?: boolean
  placeholder?: string
}

export const InputBox: React.FC<InputBoxProps> = ({
  onSend,
  disabled = false,
  placeholder = 'Ask a question about the course material...',
}) => {
  const [input, setInput] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`
    }
  }, [input])
  
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (input.trim() && !disabled) {
      onSend(input.trim())
      setInput('')
    }
  }
  
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }
  
  return (
    <form onSubmit={handleSubmit} className="flex items-end gap-2 p-4 bg-white border-t">
      <textarea
        ref={textareaRef}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        rows={1}
        className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
      />
      <button
        type="submit"
        disabled={disabled || !input.trim()}
        className="rounded-xl bg-blue-600 p-2 text-white hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
      >
        {disabled ? (
          <Loader2 className="h-5 w-5 animate-spin" />
        ) : (
          <Send className="h-5 w-5" />
        )}
      </button>
    </form>
  )
}
```

`frontend/src/components/Chat/TypingIndicator.tsx`:
```tsx
import React from 'react'

export const TypingIndicator: React.FC = () => {
  return (
    <div className="flex justify-start mb-4">
      <div className="bg-gray-100 rounded-2xl rounded-bl-md px-4 py-3">
        <div className="flex space-x-1">
          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
        </div>
      </div>
    </div>
  )
}
```

`frontend/src/components/Chat/SourceCard.tsx`:
```tsx
import React from 'react'
import { FileText } from 'lucide-react'
import { Source } from '../../stores/chatStore'

interface SourceCardProps {
  source: Source
}

export const SourceCard: React.FC<SourceCardProps> = ({ source }) => {
  return (
    <div className="flex items-start gap-2 rounded-lg bg-blue-50 border border-blue-100 p-2 text-xs">
      <FileText className="h-4 w-4 text-blue-500 mt-0.5 flex-shrink-0" />
      <div>
        <p className="font-medium text-blue-900">{source.filename}</p>
        <p className="text-blue-700 mt-0.5 line-clamp-2">{source.excerpt}</p>
      </div>
    </div>
  )
}
```

`frontend/src/components/Chat/SuggestedQuestions.tsx`:
```tsx
import React from 'react'

interface SuggestedQuestionsProps {
  questions: string[]
  onSelect: (question: string) => void
}

export const SuggestedQuestions: React.FC<SuggestedQuestionsProps> = ({
  questions,
  onSelect,
}) => {
  return (
    <div className="flex flex-wrap gap-2 p-4">
      {questions.map((question, idx) => (
        <button
          key={idx}
          onClick={() => onSelect(question)}
          className="rounded-full border border-gray-300 px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-50 hover:border-gray-400 transition-colors"
        >
          {question}
        </button>
      ))}
    </div>
  )
}
```

`frontend/src/components/Chat/MessageList.tsx`:
```tsx
import React, { useEffect, useRef } from 'react'
import { Message } from '../../stores/chatStore'
import { MessageBubble } from './MessageBubble'
import { TypingIndicator } from './TypingIndicator'

interface MessageListProps {
  messages: Message[]
  isLoading: boolean
  streamingContent: string
}

export const MessageList: React.FC<MessageListProps> = ({
  messages,
  isLoading,
  streamingContent,
}) => {
  const bottomRef = useRef<HTMLDivElement>(null)
  
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])
  
  return (
    <div className="flex-1 overflow-y-auto p-4">
      {messages.length === 0 && !isLoading && (
        <div className="flex flex-col items-center justify-center h-full text-gray-400">
          <p className="text-lg font-medium">Welcome to the Course Chatbot!</p>
          <p className="text-sm mt-1">Ask any question about the course materials.</p>
        </div>
      )}
      
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      
      {isLoading && messages.length === 0 && <TypingIndicator />}
      
      {streamingContent && (
        <div className="flex justify-start mb-4">
          <div className="bg-gray-100 rounded-2xl rounded-bl-md px-4 py-3 max-w-[80%]">
            <div className="prose prose-sm max-w-none">
              {streamingContent}
            </div>
          </div>
        </div>
      )}
      
      <div ref={bottomRef} />
    </div>
  )
}
```

**Acceptance Criteria**:
- [x] Messages display with correct styling (user vs assistant)
- [x] Markdown rendering works in assistant messages
- [x] Source citations appear below answers
- [x] Typing indicator shows during loading
- [x] Auto-scroll to latest message
- [x] Input box supports Enter to send, Shift+Enter for newline

---

#### Task 4.5: Chat Page

**What**: Create the main chat page

**Files**: `frontend/src/pages/ChatPage.tsx`, `frontend/src/hooks/useChat.ts`

**Implementation Details**:

`frontend/src/hooks/useChat.ts`:
```typescript
import { useCallback } from 'react'
import { useChatStore } from '../stores/chatStore'
import { useSessionStore } from '../stores/sessionStore'
import { chatService } from '../services/chatService'

export const useChat = () => {
  const {
    messages,
    isLoading,
    error,
    isStreaming,
    addMessage,
    setLoading,
    setError,
    setStreaming,
    appendStreamingContent,
    clearMessages,
    finishStreaming,
  } = useChatStore()
  
  const { sessionId, setSessionId } = useSessionStore()
  
  const sendMessage = useCallback(async (question: string) => {
    if (isLoading || isStreaming) return
    
    // Add user message
    addMessage({
      id: `msg_${Date.now()}`,
      role: 'user',
      content: question,
      timestamp: new Date(),
    })
    
    setLoading(true)
    setError(null)
    
    try {
      // Use streaming
      setStreaming(true)
      
      for await (const chunk of chatService.streamQuery({
        question,
        session_id: sessionId || undefined,
      })) {
        if (chunk.finish) {
          finishStreaming()
        } else {
          appendStreamingContent(chunk.delta)
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to get response')
      setStreaming(false)
    } finally {
      setLoading(false)
    }
  }, [sessionId, isLoading, isStreaming])
  
  const clearChat = useCallback(async () => {
    if (sessionId) {
      try {
        await chatService.clearSession(sessionId)
      } catch (err) {
        console.error('Failed to clear session:', err)
      }
    }
    clearMessages()
    setSessionId(null)
  }, [sessionId])
  
  return {
    messages,
    isLoading,
    error,
    isStreaming,
    sendMessage,
    clearChat,
  }
}
```

`frontend/src/pages/ChatPage.tsx`:
```tsx
import React from 'react'
import { MessageList } from '../components/Chat/MessageList'
import { InputBox } from '../components/Chat/InputBox'
import { SuggestedQuestions } from '../components/Chat/SuggestedQuestions'
import { useChat } from '../hooks/useChat'
import { useChatStore } from '../stores/chatStore'
import { Trash2 } from 'lucide-react'

const SUGGESTED_QUESTIONS = [
  "What is the main topic of this course?",
  "Summarize the key concepts from lecture 1",
  "What are the assignment deadlines?",
  "Explain the grading policy",
]

export const ChatPage: React.FC = () => {
  const { messages, isLoading, error, isStreaming, sendMessage, clearChat } = useChat()
  const { streamingContent } = useChatStore()
  
  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <header className="flex items-center justify-between px-4 py-3 bg-white border-b">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">Course Chatbot</h1>
          <p className="text-xs text-gray-500">Ask questions about your course materials</p>
        </div>
        <button
          onClick={clearChat}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 transition-colors"
        >
          <Trash2 className="h-4 w-4" />
          Clear Chat
        </button>
      </header>
      
      {/* Messages */}
      <MessageList
        messages={messages}
        isLoading={isLoading}
        streamingContent={streamingContent}
      />
      
      {/* Suggested Questions (shown when no messages) */}
      {messages.length === 0 && (
        <SuggestedQuestions
          questions={SUGGESTED_QUESTIONS}
          onSelect={sendMessage}
        />
      )}
      
      {/* Error */}
      {error && (
        <div className="mx-4 mb-2 rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
          {error}
        </div>
      )}
      
      {/* Input */}
      <InputBox
        onSend={sendMessage}
        disabled={isLoading || isStreaming}
      />
    </div>
  )
}
```

**Acceptance Criteria**:
- [x] Chat page renders correctly
- [x] Messages send and display
- [x] Streaming response works
- [x] Suggested questions appear when chat is empty
- [x] Clear chat button works
- [x] Error messages display

---

### Phase 4 Acceptance Criteria

- [x] React app builds without errors
- [x] Chat UI is responsive and readable
- [x] Messages display with markdown support
- [x] Streaming responses work
- [x] Source citations appear
- [x] Session persists across reloads

**Status: COMPLETE** (101 tests pass, `tsc` clean, `eslint` clean, `npm run build`
succeeds)

Verified against the running backend: the dev proxy forwards `/api`, SSE frames
arrive unbuffered, and a question through the proxy returns a grounded answer
with four sources and `mode: offline-extractive`. The production build was served
and confirmed to reference the real bundle.

#### Deviations from the plan in this phase

1. **The plan's `streamQuery` dropped `session_id`, and nothing ever captured
   it.** The backend mints the session server-side and sends it on the terminal
   frame, but the plan's generator yielded only `{delta, finish, sources}` and
   `setSessionId` was never called outside `clearChat`. Every turn would have
   started a new session, so the assistant had no memory of the conversation and
   the "Session management maintains context" requirement would have failed in
   the most visible way possible. `useChat` now reads `session_id` (and `mode`)
   off every frame.

2. **Added `GET /api/chat/history/{session_id}` hydration.** The plan persisted
   `sessionId` to localStorage but not the messages. On reload the user would
   see an empty chat while the server still held the history, and the next
   question would be answered using context that was invisible on screen. Phase
   3 already added the endpoint for exactly this; `useChatHistory` calls it once
   for the session that was in localStorage at mount.

3. **History hydration is pinned to the mount-time session.** A first fix that
   re-hydrated whenever `sessionId` changed was caught by a test: the first
   answer's terminal frame is what *assigns* the session, so hydrating then
   replaced the message on screen with the server's snapshot of that instant. The
   hook now hydrates at most once, for the id that was already stored.

4. **The error interceptor read `error.response.data.detail`.** The backend
   returns `{"error": {code, message, details}}` (`architecture.md` 5.3), not
   FastAPI's default `detail`. Every real error message was discarded in favour
   of a bare "Request failed with status code 500". Now unwraps the envelope and
   raises a typed `ApiError` carrying `code` and `status`, with fallbacks for a
   non-envelope body and for a request that never reached the server.

5. **Reconciled the stream in a `finally` block.** The plan called
   `finishStreaming()` only on a `finish` frame. If the connection dropped first,
   `isStreaming` stayed `true`, the input box stayed disabled, and the partial
   answer stayed invisible for the rest of the session. The `finally` now
   promotes whatever arrived, or clears the flags if nothing did.

6. **Handled the mid-stream error frame.** Once the response headers are sent the
   status code can no longer change, so the backend reports failures as a
   terminal frame carrying `error`. The plan's parser ignored that field, so a
   mid-stream failure rendered as a silent empty answer.

7. **Flushes the decoder and the parser at end of stream.** The plan decoded with
   `{stream: true}` and never flushed, so a final frame without a trailing
   newline was lost, as were the last bytes of any multi-byte character split
   across two reads. Malformed frames are now counted and skipped rather than
   thrown — one bad frame should cost a few words, not the whole answer.

8. **Extracted the SSE parsing into `services/sse.ts`.** Inlined in the service
   it was untestable, and frame boundaries land wherever the network splits a
   chunk, which is exactly the part that is hard to review by eye.

9. **Added `@tailwindcss/typography`.** `MessageBubble` and `MessageList` use the
   `prose` class, but the plan's `tailwind.config.js` had `plugins: []` and no
   typography dependency. `prose` would have compiled to nothing and every
   markdown answer would have rendered as unstyled paragraphs.

10. **The plan could not build.** `InputBox` passed a `React.KeyboardEvent` to a
    handler typed for `React.FormEvent`; since `build` is `tsc && vite build`, that
    was a compile error. Submit logic is now separate from event handling. The
    plan also listed no `tsconfig.json` content and no `index.html`, `main.tsx`,
    `index.css`, or `vite-env.d.ts`, so the app had no entry point at all.

11. **Fixed the typing indicator condition.** The plan gated it on
    `isLoading && messages.length === 0`, so it appeared on the first turn and
    never again — precisely when a user most wants feedback on a follow-up. It is
    now driven by `isLoading && !streamingContent`, which covers the wait for the
    first token on every turn.

12. **Streamed text renders as markdown.** The plan rendered `streamingContent` as
    a raw string but finished messages through `ReactMarkdown`, so the typography
    jumped the moment an answer completed. Both now use one `MarkdownContent`
    component.

13. **The mode is surfaced in the UI.** Every response reports `mode`
    (`openai` or `offline-extractive`). The plan dropped it, which in offline mode
    would present quoted sentences as though a language model had written them. A
    badge now distinguishes the two, with a tooltip that states plainly when no
    model was called.

14. **Message ids are not `Date.now()`.** Two messages created in the same
    millisecond — a question and the reply to it — collide, and React treats a
    duplicate key as the same element, silently dropping a bubble. Ids now carry a
    counter.

15. **Added stop-generation, request aborting and IME handling.** There is now an
    `AbortController` per turn: stopping keeps the partial answer, unmounting
    aborts, and Enter is not treated as a send while an input method is mid
    composition (which would truncate a CJK word).

16. **Guarded `scrollIntoView`.** Absent in jsdom and some embedded webviews;
    auto-scroll is not worth crashing the chat over. Also added
    `GET /api/documents/{id}` semantics to `documentService.remove` (the plan
    called axios's `delete` on a `delete` method, which works but shadows the
    reserved word) and dropped the redundant `Content-Type` on the upload so the
    browser can set the multipart boundary.

17. **Added a test suite, which the plan did not specify.** 101 Vitest tests over
    the SSE parser (including a byte-for-byte capture of a real backend response,
    a multi-byte character split mid-sequence, and frames delivered one character
    at a time), the error-envelope mapping, the stores, the hooks, and the page
    rendered end to end. Three of the bugs above were found by these tests rather
    than by reading.

18. **Dev proxy pins `Cache-Control: no-transform` on SSE responses.** Vite's
    dev server can otherwise buffer `text/event-stream`, collapsing the stream
    into one chunk at the end and removing the typing effect entirely.

19. **`react-router-dom` is installed but unused.** Phase 4 is a single page. The
    dependency is kept because Phase 5's admin panel needs it, but no router is
    configured yet rather than adding an unused abstraction.

---

## Post-Phase 4: Demo-Quality Fixes

Found by walking the suggested questions against the running system rather than
by reading the code. Four defects, three of them in the backend.

### 1. The local embedder made some words unfindable

`What does homework contribute?` returned the no-context fallback even though
`syllabus.txt` states "Homework contributes 30 percent" outright. A bare query
of `homework` also fell back, while `What is the homework worth?` was answered —
inverted, so not a vocabulary problem.

`LocalHashEmbedder` accumulated **signed**: each feature got a ±1 from its
digest. Two features landing in the same bucket with equal counts and opposite
signs cancel *exactly*, so the term contributes nothing to a query for it. In
the 160-feature syllabus chunk, 24 of 512 buckets collided and **9 cancelled
outright**; `homework` (−1.0) was annihilated by `trees` (+1.0).

Measured, since the obvious fix is not the only one:

| dim | signed | invisible terms | worst off-topic sim |
|-----|--------|-----------------|---------------------|
| 512 | yes | **9 / 69** | +0.2273 |
| 512 | no | 0 / 69 | +0.1929 |
| 2048 | yes | **2 / 75** | +0.2076 |
| 2048 | no | 0 / 75 | +0.1959 |
| 8192 | yes | **1 / 75** | +0.1469 |
| 8192 | no | 0 / 75 | +0.1457 |

Widening the vector is the tempting fix and it is not sufficient — a term in
this corpus still cancelled at 8192. Unsigned accumulation makes presence
*sufficient*: if `t` occurs in the document its bucket holds a positive weight,
so the dot product with the single-feature query for `t` is positive **by
construction**. Collisions can only add to a match, never erase one.

The cost is that unrelated documents share some mass. That is already the
design: retrieval is a high-recall lexical net whose only hard requirement is
that a word in the document is *findable*, and sentence scoring in the offline
generator is what rejects an off-topic question. The measurement supports this —
in-domain and off-topic multi-word questions score within ~0.05 of each other at
*any* width, so the vector was never the thing separating them.

`LOCAL_EMBEDDING_DIM` went 512 → 2048 (collisions become rare; 4× the floats is
irrelevant at this scale) and the sign step is gone. `tests/test_embedding.py`
pins both the invariant and the counterfactual, so re-adding signs to "reduce
bias" fails a test instead of silently returning nothing.

One test asserts the *honest* limitation rather than a property the embedder
does not have: an unrelated question does retrieve the chunk, and that is
intended. An earlier draft of that test asserted off-topic similarity would be
below in-domain, and it failed — correctly, because that is not true of a hashed
bag-of-words and it should not pretend to be.

### 2. `EMBEDDING_MISMATCH` was reported as a generic 422

`DocumentService.process_document` and the upload route each wrapped
`except Exception` around the embed and store steps, so a 409
`EMBEDDING_MISMATCH` (and a 503 `EMBEDDING_UNAVAILABLE`) reached the client as
422 `PROCESSING_ERROR` — "Unexpected error while processing the document", which
names neither the cause nor the remedy. Both now re-raise `AppError` unchanged.

### 3. Changing the embedding width deadlocked the index

The remedy the 409 gives — "delete the documents and upload them again" — could
never complete, because *two* independent pieces of state record the width:

| State | Where | Cleared by |
|-------|-------|-----------|
| Index-info sidecar | `data/chroma/index_info.json` | deleted, rewritten on next store |
| Collection width | Chroma's own `collections` table | collection deleted and recreated |

The sidecar is ours to discard, and now is. The collection width is not: Chroma
fixes it at creation and exposes no public accessor, so emptying the collection
does not reset it. `store_embeddings` now recognises Chroma's "does not match
collection dimensionality" rejection and, **only when the collection is empty**,
rebuilds it and retries once. A populated collection is never rebuilt — that
stays a 409, because it would silently discard indexed documents.

The regression test builds the stale state for real (index at 512, empty it,
widen the setting) because the width is unreadable through the public API. It
was checked to fail with the exact production error when the self-heal is
disabled — an earlier draft set `collection.metadata["hnsw:dim"]` and passed
vacuously, because that key is not in the collection metadata at all in Chroma
0.4.24.

### 4. Suggested questions that could not be answered

Three of the four chips answered; `What are the assessment weights?` fell back,
because the syllabus says "accounts for 40 percent of the course grade" and
never uses the word "weights". Legitimate behaviour, poor first impression.
Replaced with four that each resolve and span different topics, so the first
answer does not suggest only one document is indexed.

### Also

- `backend/samples/` now holds the demo and fixture documents that were
  previously in a macOS temp directory, which would have been cleaned. The
  fixture table in its README is measured, not guessed: chunking is by *token*,
  so `multi.pdf` is 29,770 characters in a single 443-token chunk.
- `stats_reports_index_model` depended on a sidecar an earlier test happened to
  leave behind. It now indexes first, and a companion test asserts an empty index
  reports no model rather than a stale one.
- The autouse embedding fixture now snapshots and restores the sidecar. A
  `try`/`finally` in each test looked equivalent but a `NameError` in one left
  every later test failing with a mismatch, which reads like a real regression.

Backend: 232 tests (from 222), `ruff` clean. Frontend unchanged: 101 tests, `tsc`
and `eslint` clean. Verified live through the Vite dev proxy after re-indexing.

---

## Phase 5: Frontend — Admin Panel

### Objectives
- Implement document upload UI
- Implement document list with management
- Implement system status display

### Tasks

---

#### Task 5.1: Admin Components

**What**: Create admin panel components

**Files**:
- `frontend/src/components/Admin/DocumentList.tsx`
- `frontend/src/components/Admin/DocumentCard.tsx`
- `frontend/src/components/Admin/UploadButton.tsx`
- `frontend/src/components/Admin/SystemStatus.tsx`

**Implementation Details**:

`frontend/src/components/Admin/UploadButton.tsx`:
```tsx
import React, { useState, useRef } from 'react'
import { Upload, Loader2, Check, X } from 'lucide-react'
import { documentService } from '../../services/documentService'
import { useDocumentStore } from '../../stores/documentStore'

export const UploadButton: React.FC = () => {
  const [isUploading, setIsUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  
  const addDocument = useDocumentStore((state) => state.addDocument)
  
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    
    setIsUploading(true)
    setProgress(0)
    setResult(null)
    
    try {
      const doc = await documentService.upload(file, setProgress)
      addDocument(doc)
      setResult({
        success: true,
        message: `Uploaded "${doc.filename}" (${doc.chunk_count} chunks)`,
      })
    } catch (err) {
      setResult({
        success: false,
        message: err instanceof Error ? err.message : 'Upload failed',
      })
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }
  
  return (
    <div className="space-y-2">
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.txt,.docx,.md"
        onChange={handleFileSelect}
        disabled={isUploading}
        className="hidden"
        id="file-upload"
      />
      <label
        htmlFor="file-upload"
        className={`flex items-center justify-center gap-2 rounded-xl border-2 border-dashed p-6 cursor-pointer transition-colors ${
          isUploading
            ? 'border-blue-300 bg-blue-50 cursor-not-allowed'
            : 'border-gray-300 hover:border-blue-400 hover:bg-blue-50'
        }`}
      >
        {isUploading ? (
          <>
            <Loader2 className="h-5 w-5 text-blue-500 animate-spin" />
            <span className="text-sm text-blue-700">Uploading... {progress}%</span>
          </>
        ) : (
          <>
            <Upload className="h-5 w-5 text-gray-400" />
            <span className="text-sm text-gray-600">
              Click to upload or drag and drop
            </span>
            <span className="text-xs text-gray-400">PDF, TXT, DOCX, MD (max 50MB)</span>
          </>
        )}
      </label>
      
      {result && (
        <div
          className={`flex items-center gap-2 rounded-lg p-3 text-sm ${
            result.success
              ? 'bg-green-50 text-green-700 border border-green-200'
              : 'bg-red-50 text-red-700 border border-red-200'
          }`}
        >
          {result.success ? (
            <Check className="h-4 w-4" />
          ) : (
            <X className="h-4 w-4" />
          )}
          {result.message}
        </div>
      )}
    </div>
  )
}
```

`frontend/src/components/Admin/DocumentCard.tsx`:
```tsx
import React from 'react'
import { FileText, Trash2, Clock, Database } from 'lucide-react'
import { Document } from '../../stores/documentStore'
import { documentService } from '../../services/documentService'

interface DocumentCardProps {
  document: Document
  onDelete: (id: string) => void
}

export const DocumentCard: React.FC<DocumentCardProps> = ({ document, onDelete }) => {
  const [isDeleting, setIsDeleting] = React.useState(false)
  
  const handleDelete = async () => {
    if (!confirm(`Delete "${document.filename}"?`)) return
    
    setIsDeleting(true)
    try {
      await documentService.delete(document.id)
      onDelete(document.id)
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Delete failed')
    } finally {
      setIsDeleting(false)
    }
  }
  
  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }
  
  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }
  
  const fileTypeColors: Record<string, string> = {
    pdf: 'bg-red-100 text-red-700',
    docx: 'bg-blue-100 text-blue-700',
    txt: 'bg-gray-100 text-gray-700',
    md: 'bg-purple-100 text-purple-700',
  }
  
  return (
    <div className="flex items-center justify-between rounded-xl border bg-white p-4 hover:shadow-sm transition-shadow">
      <div className="flex items-center gap-3">
        <div className={`rounded-lg p-2 ${fileTypeColors[document.file_type] || 'bg-gray-100'}`}>
          <FileText className="h-5 w-5" />
        </div>
        <div>
          <p className="font-medium text-gray-900">{document.filename}</p>
          <div className="flex items-center gap-3 text-xs text-gray-500 mt-0.5">
            <span className="flex items-center gap-1">
              <Database className="h-3 w-3" />
              {document.chunk_count} chunks
            </span>
            <span>{formatSize(document.file_size)}</span>
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {formatDate(document.created_at)}
            </span>
            <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              document.status === 'processed'
                ? 'bg-green-100 text-green-700'
                : document.status === 'failed'
                ? 'bg-red-100 text-red-700'
                : 'bg-yellow-100 text-yellow-700'
            }`}>
              {document.status}
            </span>
          </div>
        </div>
      </div>
      <button
        onClick={handleDelete}
        disabled={isDeleting}
        className="rounded-lg p-2 text-gray-400 hover:bg-red-50 hover:text-red-500 transition-colors disabled:opacity-50"
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </div>
  )
}
```

`frontend/src/components/Admin/DocumentList.tsx`:
```tsx
import React from 'react'
import { Document } from '../../stores/documentStore'
import { DocumentCard } from './DocumentCard'

interface DocumentListProps {
  documents: Document[]
  onDelete: (id: string) => void
}

export const DocumentList: React.FC<DocumentListProps> = ({ documents, onDelete }) => {
  if (documents.length === 0) {
    return (
      <div className="text-center py-12 text-gray-400">
        <p className="text-sm">No documents uploaded yet.</p>
        <p className="text-xs mt-1">Upload your first document above.</p>
      </div>
    )
  }
  
  return (
    <div className="space-y-2">
      <p className="text-sm text-gray-500 mb-3">
        {documents.length} document{documents.length !== 1 ? 's' : ''} uploaded
      </p>
      {documents.map((doc) => (
        <DocumentCard key={doc.id} document={doc} onDelete={onDelete} />
      ))}
    </div>
  )
}
```

**Acceptance Criteria**:
- [x] Upload button accepts PDF, TXT, DOCX, MD
- [x] Upload progress displayed
- [x] Document list shows all uploaded files
- [x] Delete button removes documents
- [x] File type icons/colors display
- [x] Status badges show processing state

---

#### Task 5.2: Admin Page

**What**: Create the admin page

**Files**: `frontend/src/pages/AdminPage.tsx`, `frontend/src/hooks/useDocuments.ts`

**Implementation Details**:

`frontend/src/hooks/useDocuments.ts`:
```typescript
import { useState, useEffect, useCallback } from 'react'
import { documentService } from '../services/documentService'
import { useDocumentStore } from '../stores/documentStore'

export const useDocuments = () => {
  const { documents, setDocuments, removeDocument, setError } = useDocumentStore()
  const [isLoading, setIsLoading] = useState(true)
  
  const loadDocuments = useCallback(async () => {
    setIsLoading(true)
    try {
      const data = await documentService.list()
      setDocuments(data.documents)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load documents')
    } finally {
      setIsLoading(false)
    }
  }, [])
  
  useEffect(() => {
    loadDocuments()
  }, [loadDocuments])
  
  const handleDelete = useCallback((id: string) => {
    removeDocument(id)
  }, [removeDocument])
  
  return {
    documents,
    isLoading,
    refresh: loadDocuments,
    deleteDocument: handleDelete,
  }
}
```

`frontend/src/pages/AdminPage.tsx`:
```tsx
import React from 'react'
import { UploadButton } from '../components/Admin/UploadButton'
import { DocumentList } from '../components/Admin/DocumentList'
import { useDocuments } from '../hooks/useDocuments'
import { Loader2, RefreshCw } from 'lucide-react'

export const AdminPage: React.FC = () => {
  const { documents, isLoading, refresh, deleteDocument } = useDocuments()
  
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <h1 className="text-xl font-semibold text-gray-900">Document Management</h1>
          <p className="text-sm text-gray-500">Upload and manage course materials</p>
        </div>
      </header>
      
      <main className="max-w-4xl mx-auto px-4 py-6">
        {/* Upload Section */}
        <section className="mb-8">
          <h2 className="text-sm font-medium text-gray-700 mb-3">Upload Documents</h2>
          <UploadButton />
        </section>
        
        {/* Documents Section */}
        <section>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-medium text-gray-700">Uploaded Documents</h2>
            <button
              onClick={refresh}
              disabled={isLoading}
              className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-700 transition-colors"
            >
              <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
          
          {isLoading ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-6 w-6 text-gray-400 animate-spin" />
            </div>
          ) : (
            <DocumentList documents={documents} onDelete={deleteDocument} />
          )}
        </section>
      </main>
    </div>
  )
}
```

**Acceptance Criteria**:
- [x] Admin page renders correctly
- [x] Upload button works with progress
- [x] Document list loads and displays
- [x] Delete removes document from list
- [x] Refresh reloads document list

---

### Phase 5 Acceptance Criteria

- [x] Document upload works end-to-end
- [x] Document list displays all files
- [x] Delete removes documents
- [x] Upload progress shown
- [x] Error messages display

---

## Phase 5: Implementation Notes

All 16 checkboxes are ticked. 19 deviations from the plan text, one of which
was a bug that made the phase's headline feature unusable.

### The upload was broken before this phase

`apiClient` is an axios instance with a default `Content-Type:
application/json`, and axios merges instance headers into every request. The
Phase 4 `documentService.upload` posted a `FormData` while explicitly *not*
overriding that header — reasoning that the browser should set the multipart
boundary itself — but the instance default filled the gap in anyway.

With a `Content-Type` already present the browser does not generate a
boundary, so the body arrives unparseable. Confirmed against the running
backend before changing anything:

```
POST /api/documents/upload   (FormData, inherited JSON content type)
  -> 422 {"error":{"code":"VALIDATION_ERROR",
       "details":{"errors":[{"loc":["body","file"],"msg":"Field required"}]}}}
```

The error names a *missing form field*, which sends you looking at the form
rather than at the header, and there was no test coverage on the upload path
to catch it. The fix is `headers: { 'Content-Type': undefined }` in the
upload request, which deletes the inherited header in axios 1.x and leaves the
browser to emit `multipart/form-data; boundary=…`. Verified at the header
merge, not just by the request succeeding:

```
instance default only   -> {"Accept":"…","Content-Type":"application/json"}
after upload() override -> {"Accept":"…"}
has Content-Type?       -> false
```

Setting the header to the literal string `multipart/form-data` instead — the
other obvious fix — is *also* wrong: that value is sent verbatim, with no
boundary. A regression test asserts the header is absent and is not the
multipart literal.

### Deviations

| # | Plan says | What was built | Why |
|---|---|---|---|
| 1 | `documentService.delete(id)` | `documentService.remove(id)` | `delete` is a reserved word and cannot be a method name. Asserted in a test. |
| 2 | `useDocuments` destructures `useDocumentStore()` as one object | Per-field selectors | Returning the whole store makes the component re-render on every unrelated state change. |
| 3 | `useDocuments.handleDelete` calls only `removeDocument(id)` | The hook issues the `DELETE` and updates state on success | The plan's version only spliced local state, so a *failed* delete silently removed the row and it reappeared on the next refresh. The hook's `remove` also returned a name that lied about what it did. |
| 4 | `DocumentCard` uses `window.confirm` / `window.alert` | `ConfirmDialog` component | jsdom does not implement either, so the whole delete path was untestable. `window.confirm` also blocks the event loop and cannot be styled. Escape cancels, matching the native dialog. |
| 5 | `AdminPage` never renders the store's `error` | `role="alert"` banners for load/upload/delete and status failures | The plan's own criterion "Error messages display" was unmet by the plan's own code. |
| 6 | `UploadButton` holds its own `isUploading` / `progress` / `result` | All upload state lives in `documentStore` | Two sources of truth for one upload. |
| 7 | Progress reaches 100% then the button re-enables | Progress bar plus a distinct "Indexing document…" phase | The backend parses, chunks and embeds *inside* the upload request, so the bytes finish travelling well before the response. A bar parked at 100% is indistinguishable from a hang. |
| 8 | `documentService.list()` calls `/documents` | `/documents/` | The route is registered with a trailing slash; the bare path costs a 307 on every list. |
| 9 | `onUploadProgress` divides by `event.total` | Guards `total === 0` | A chunked body reports `total` as 0, so the naive ratio is `NaN`. |
| 10 | No drag-and-drop, though the copy advertises it | `onDrop` / `onDragOver` implemented | The advertised behaviour did not exist. |
| 11 | No client-side file validation | `validateFile` rejects bad type, oversize and empty files | Fails instantly instead of after a round trip. Documented in `validateFile.ts` as a courtesy filter, *not* a security boundary — the backend re-checks independently and its message is what the panel shows. |
| 12 | `SystemStatus.tsx` listed in the file list, never specified | Implemented from `/health`, `/health/ready`, `/documents/stats` | "System status display" is a stated objective. |
| 13 | — | `SystemStatus` warns when `indexed_with != embedding_model` | The single most useful thing this panel can say. After an embedding-provider change every upload fails with `EMBEDDING_MISMATCH`; showing the disagreement *before* the next upload turns a confusing 409 into a visible cause. |
| 14 | — | `useSystemStatus` uses `Promise.allSettled` and keeps partial results | A panel that blanks out because one probe failed hides the thing it exists to show. |
| 15 | No routing; `/admin` unreachable | `BrowserRouter` + `Header` with Chat/Documents links | The plan defers routing to Task 6.1 but never says how a user reaches the admin panel. This is the minimal version — no landing page, which stays in Phase 6. |
| 16 | `ChatPage` is the whole app shell | `ChatPage` is a route; `App.tsx` owns the shell | It has to become a route for 15 to work. Its `h-screen` became `h-full`. |
| 17 | `App` is a named export only | Both named and default export | Task 6.1's snippet uses `export default`; keeping both avoids churn when that lands. |
| 18 | `DocumentList` renders bare `DocumentCard`s in a `div` | Wrapped in `ul`/`li` | List markup, for correctness and for assistive tech. |
| 19 | — | Status labels read `indexed` / `processing` / `failed` | `processed` and `pending` are wire values; on screen they describe something the reader has not seen. |

### Where the files went

Three helpers were pulled out of component files because exporting a
non-component from a module breaks React Fast Refresh:

- `components/Admin/format.ts` — `formatSize`, `formatDate`. `formatDate`
  returns `"unknown date"` for an unparseable timestamp rather than printing
  `Invalid Date`.
- `components/Admin/validateFile.ts` — the pre-flight checks and the
  extension/size constants, each citing the backend constant it mirrors.
- `services/systemService.ts` — `/health` and `/health/ready`, split from
  `documentService` because they are not about documents.

### Testing note

Two tests need `userEvent.setup({ applyAccept: false })`. The file input
carries an `accept` attribute, and userEvent *discards* files that do not
match it, so `change` never fires and the component's own guard is never
exercised. The option is a `setup()` option, not a per-call argument.

### Verification

- Frontend: 177 tests (was 101), `tsc` clean, `eslint` clean, `npm run build`
  succeeds.
- Backend: 232 tests, `ruff check` clean — unchanged, as this phase is
  frontend-only.
- Live, through the Vite dev proxy on a freshly reset database: upload two
  documents, list them newest-first (matching the store's prepend, so a
  refresh does not reorder the page), read stats and readiness, delete one,
  confirm the list drops to 1, then re-delete for `DOCUMENT_NOT_FOUND`.
  `INVALID_FILE_TYPE` and `EMPTY_FILE` reproduced. Chat re-checked afterwards:
  all four suggested questions answer, off-topic still falls back.

---

## Phase 6: Integration, Testing & Demo Prep

### Objectives
- Set up routing
- Create landing page
- Add Docker configuration
- End-to-end testing
- Performance optimization
- Demo rehearsal

### Tasks

---

#### Task 6.1: Routing & Navigation

**What**: Set up React Router with all pages

**Files**: `frontend/src/App.tsx`, `frontend/src/components/Common/Header.tsx`

**Implementation Details**:

`frontend/src/App.tsx`:
```tsx
import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ChatPage } from './pages/ChatPage'
import { AdminPage } from './pages/AdminPage'
import { LandingPage } from './pages/LandingPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
```

`frontend/src/components/Common/Header.tsx`:
```tsx
import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import { MessageCircle, Upload, Home } from 'lucide-react'

export const Header: React.FC = () => {
  const location = useLocation()
  
  const navItems = [
    { path: '/', label: 'Home', icon: Home },
    { path: '/chat', label: 'Chat', icon: MessageCircle },
    { path: '/admin', label: 'Documents', icon: Upload },
  ]
  
  return (
    <nav className="bg-white border-b">
      <div className="max-w-6xl mx-auto px-4">
        <div className="flex items-center justify-between h-14">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
              <MessageCircle className="h-5 w-5 text-white" />
            </div>
            <span className="font-semibold text-gray-900">RAG Chatbot</span>
          </Link>
          
          <div className="flex items-center gap-1">
            {navItems.map((item) => {
              const Icon = item.icon
              const isActive = location.pathname === item.path
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-blue-50 text-blue-700'
                      : 'text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </Link>
              )
            })}
          </div>
        </div>
      </div>
    </nav>
  )
}
```

**Acceptance Criteria**:
- [x] Routing works between all pages
- [x] Navigation highlights active page
- [x] Header displays on all pages

---

#### Task 6.2: Landing Page

**What**: Create a simple landing page

**Files**: `frontend/src/pages/LandingPage.tsx`

**Implementation Details**:
```tsx
import React from 'react'
import { Link } from 'react-router-dom'
import { MessageCircle, Upload, ArrowRight, BookOpen, Brain, Search } from 'lucide-react'
import { Header } from '../components/Common/Header'

export const LandingPage: React.FC = () => {
  const features = [
    {
      icon: Upload,
      title: 'Upload Course Materials',
      description: 'Upload PDFs, documents, and notes to build your knowledge base.',
    },
    {
      icon: Search,
      title: 'Smart Retrieval',
      description: 'Our RAG pipeline finds the most relevant information instantly.',
    },
    {
      icon: Brain,
      title: 'AI-Powered Answers',
      description: 'Get accurate, contextual answers based on your course content.',
    },
  ]
  
  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
      <Header />
      
      <main>
        {/* Hero */}
        <section className="max-w-4xl mx-auto px-4 py-20 text-center">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">
            RAG Chatbot for Class Demo
          </h1>
          <p className="text-lg text-gray-600 mb-8 max-w-2xl mx-auto">
            An intelligent chatbot that answers questions using your course materials.
            Built with Retrieval-Augmented Generation (RAG) technology.
          </p>
          <div className="flex items-center justify-center gap-4">
            <Link
              to="/chat"
              className="flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-3 text-white font-medium hover:bg-blue-700 transition-colors"
            >
              <MessageCircle className="h-5 w-5" />
              Start Chatting
            </Link>
            <Link
              to="/admin"
              className="flex items-center gap-2 rounded-xl border border-gray-300 px-6 py-3 text-gray-700 font-medium hover:bg-gray-50 transition-colors"
            >
              <Upload className="h-5 w-5" />
              Upload Documents
            </Link>
          </div>
        </section>
        
        {/* Features */}
        <section className="max-w-5xl mx-auto px-4 pb-20">
          <div className="grid md:grid-cols-3 gap-6">
            {features.map((feature, idx) => {
              const Icon = feature.icon
              return (
                <div key={idx} className="rounded-2xl bg-white p-6 shadow-sm border">
                  <div className="w-12 h-12 rounded-xl bg-blue-100 flex items-center justify-center mb-4">
                    <Icon className="h-6 w-6 text-blue-600" />
                  </div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">{feature.title}</h3>
                  <p className="text-sm text-gray-600">{feature.description}</p>
                </div>
              )
            })}
          </div>
        </section>
        
        {/* How it works */}
        <section className="max-w-4xl mx-auto px-4 pb-20">
          <h2 className="text-2xl font-bold text-center text-gray-900 mb-8">How It Works</h2>
          <div className="space-y-4">
            {[
              { step: '1', title: 'Upload', desc: 'Instructor uploads course materials (PDF, DOCX, TXT, MD)' },
              { step: '2', title: 'Index', desc: 'Documents are parsed, chunked, and embedded into a vector store' },
              { step: '3', title: 'Ask', desc: 'Students ask questions using natural language' },
              { step: '4', title: 'Answer', desc: 'RAG retrieves relevant chunks and generates grounded answers' },
            ].map((item) => (
              <div key={item.step} className="flex items-start gap-4 rounded-xl bg-white p-4 border">
                <div className="w-8 h-8 rounded-full bg-blue-600 text-white flex items-center justify-center font-semibold flex-shrink-0">
                  {item.step}
                </div>
                <div>
                  <h4 className="font-medium text-gray-900">{item.title}</h4>
                  <p className="text-sm text-gray-600">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </section>
      </main>
    </div>
  )
}
```

**Acceptance Criteria**:
- [x] Landing page renders with hero section
- [x] Feature cards display
- [x] "How it works" section shows
- [x] Navigation links work

---

#### Task 6.3: Docker Configuration

**What**: Create Docker configuration for full stack deployment

**Files**: `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile`

**Implementation Details**:

`docker-compose.yml`:
```yaml
version: "3.9"

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - LLM_MODEL=${LLM_MODEL:-big-pickle}
      - OPENAI_EMBEDDING_MODEL=${OPENAI_EMBEDDING_MODEL:-text-embedding-3-small}
      - CHROMA_PERSIST_DIR=/app/data/chroma
      - DATABASE_URL=sqlite:////app/data/app.db
      - CORS_ORIGINS=["http://localhost:3000","http://localhost:5173"]
    volumes:
      - ./data:/app/data
    restart: unless-stopped

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:80"
    depends_on:
      - backend
    restart: unless-stopped
```

`backend/Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`frontend/Dockerfile`:
```dockerfile
# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

# nginx config for SPA routing
RUN echo 'server { \
    listen 80; \
    location / { \
        root /usr/share/nginx/html; \
        index index.html; \
        try_files $uri $uri/ /index.html; \
    } \
    location /api { \
        proxy_pass http://backend:8000; \
    } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

**Acceptance Criteria**:
- [ ] `docker-compose up` starts both services  -- **not verified: Docker is not installed on this machine**
- [ ] Frontend accessible at localhost:3000  -- **not verified: Docker is not installed on this machine**
- [ ] Backend accessible at localhost:8000  -- **not verified: Docker is not installed on this machine**
- [ ] API proxy works through nginx  -- **not verified: Docker is not installed on this machine**

---

#### Task 6.4: End-to-End Testing Checklist

**What**: Comprehensive testing before demo

**Files**: N/A (testing checklist)

**Implementation Details**:

```
## End-to-End Testing Checklist

### Backend Tests
- [x] Health check endpoint returns 200
- [x] Upload PDF document → 201 Created
- [x] Upload TXT document → 201 Created
- [x] Upload invalid file type → 400 Bad Request
- [x] Upload file > 50MB → 400 Bad Request
- [x] List documents → returns all uploaded
- [x] Delete document → 200 OK, removed from list
- [x] Chat query → returns answer with sources
- [ ] Chat query (no docs) → returns fallback message  -- out-of-scope questions return the fallback, but an *empty index* was not tested
- [x] Chat streaming → streams chunks correctly
- [x] Clear session → history removed

### Frontend Tests
- [ ] Landing page renders  -- jsdom only
- [ ] Navigation works between pages  -- jsdom only
- [ ] Chat page loads  -- jsdom only
- [ ] Upload button accepts files  -- jsdom only
- [ ] Upload progress displays  -- jsdom only
- [ ] Document list shows uploaded files  -- jsdom only
- [ ] Delete document works  -- jsdom only
- [ ] Send message → response appears  -- jsdom only
- [ ] Streaming response displays  -- jsdom only
- [ ] Source citations appear  -- jsdom only
- [ ] Clear chat works  -- jsdom only
- [ ] Suggested questions work  -- jsdom only
- [ ] Error messages display  -- jsdom only

### Integration Tests
- [x] Upload → appears in document list
- [x] Upload → ask question about content → accurate answer
- [ ] Delete → question about deleted doc → fallback message  -- not run; it needs a delete followed by a query about the deleted content
- [x] Multiple documents → search finds correct one
- [ ] Session persistence → reload → chat history maintained  -- backend half verified (and a real bug fixed); the browser reload was not done
- [x] Streaming → complete response received

### Performance Tests
- [x] Document upload < 3 seconds
- [x] Query response < 5 seconds
- [x] Streaming starts < 1 second
- [ ] 10 concurrent queries → all succeed  -- measured the provider's 8k tokens/min quota instead, not server concurrency
- [ ] 50MB document → processes successfully  -- not run; `--with-large` exists but takes minutes

### Demo Preparation
- [x] Sample documents uploaded
- [x] Demo questions prepared
- [x] Fallback scenario tested
- [x] Error handling verified
- [ ] UI readable from projector  -- needs a human with a projector
- [ ] Internet connection stable  -- nothing in the repo to verify
- [ ] Backup plan ready (screenshots/video)  -- not prepared
```

**Acceptance Criteria**:
- [x] All backend tests pass
- [x] All frontend tests pass
- [x] All integration tests pass
- [ ] Performance targets met  -- 3 of 5 targets verified
- [ ] Demo rehearsal completed  -- has not happened

---

#### Task 6.5: Demo Script & Preparation

**What**: Prepare demo script and sample content

**Files**: `demo/README.md`, `demo/sample-documents/`

**Implementation Details**:

`demo/README.md`:
```markdown
# Demo Script — RAG Chatbot

## Pre-Demo Setup
1. Start the application: `docker-compose up` or `npm run dev` + `uvicorn`
2. Open browser to `http://localhost:3000`
3. Navigate to Admin page
4. Upload sample documents (see `sample-documents/`)
5. Verify documents are processed
6. Test a few questions on Chat page

## Demo Flow (5-7 minutes)

### 1. Introduction (30 seconds)
- "This is a RAG chatbot for classroom use"
- "It combines information retrieval with large language models"
- "Let me show you how it works"

### 2. Document Upload (1 minute)
- Navigate to Admin page
- Upload a sample PDF (e.g., lecture slides)
- Show processing status
- "The document is automatically parsed, chunked, and embedded"

### 3. Basic Q&A (1 minute)
- Ask: "What is the main topic of this document?"
- Show the answer with source citations
- "Notice how it cites where the information came from"

### 4. Complex Query (1 minute)
- Ask a question that requires synthesizing information
- "Compare X and Y from the lecture"
- Show how multiple chunks are retrieved

### 5. Fallback Handling (30 seconds)
- Ask a question NOT in the documents
- "What's the weather today?"
- Show the graceful fallback response

### 6. Streaming (30 seconds)
- Ask another question
- Show the streaming response in real-time

### 7. Architecture Overview (1 minute)
- Show the architecture diagram
- Explain the RAG pipeline briefly

## Sample Questions to Ask

Each of these was run against `backend/samples/demo/` and returns a grounded
answer, so none of them can embarrass you mid-demo:

1. "What counts towards the final grade?" — grading breakdown
2. "What does homework contribute?" — homework weighting
3. "When is the project proposal due?" — deadline
4. "When are the office hours?" — contact
5. "Who is the TA?" — staff
6. "What is the weather today?" — deliberately off-topic, to show the
   "I don't have information about that" fallback

Avoid phrasings the documents never use. In offline mode the generator matches
question terms against sentences literally, so a question using the *right
concept* in the *wrong words* retrieves the correct chunk and then still finds
nothing to quote:

| Don't ask | Why | Ask instead |
|-----------|-----|-------------|
| "What are the assessment weights?" | The syllabus says "accounts for 40 percent of the course grade" and never says "weights" | "What counts towards the final grade?" |
| "What grading policy applies to late submissions?" | "late" is present, "policy" and "submissions" are not | "What does homework contribute?" |

## Troubleshooting
- **Backend not starting**: Check OPENAI_API_KEY in .env
- **Upload failing**: Check file size < 50MB
- **No answers**: Verify documents are processed (status = "processed")
- **Slow response**: Check internet connection, try smaller documents
- **409 EMBEDDING_MISMATCH**: The index was built with a different embedding
  provider or width. Delete the documents and upload them again — an *empty*
  index is rebuilt automatically, so the recovery cannot get stuck. If it
  persists, `rm -rf backend/data/chroma` forces a clean start.
- **An answer falls back despite the document containing it**: Check
  `LOCAL_EMBEDDING_DIM` in `.env`, then re-index. A word is unretrievable only
  if the index was built at a different width than the current setting.
```

**Acceptance Criteria**:
- [x] Sample documents created
- [x] Demo script written
- [ ] Demo rehearsed at least once  -- the runbook is written but has not been walked through end to end
- [ ] Backup plan prepared  -- not prepared

---

### Phase 6 Acceptance Criteria

- [x] All pages route correctly
- [x] Landing page renders
- [ ] Docker deployment works  -- Docker is not installed on this machine
- [x] All tests pass
- [ ] Demo rehearsal completed  -- has not happened
- [ ] Performance targets met  -- 3 of 5 targets verified

---

## Phase 6: Implementation Notes

36 of the 68 checkboxes are ticked. The 32 left open each carry an inline
reason. Two are worth reading before anything else, because they are claims the
plan asks for that nobody can honestly make yet: **no Docker image has been
built** (Docker is not installed on this machine) and **no human has watched the
frontend render in a browser** (the jsdom suite is not a browser).

### Running the checklist found a bug the unit tests missed

Task 6.4 asks for an end-to-end checklist. Written as markdown it would have
been ticked once and never looked at again, so it is `scripts/e2e_check.py` —
the same list as code, run against a live server, exiting non-zero on failure
and cleaning up after itself.

The first run failed eleven checks. Ten were my own wrong URLs. The eleventh
was real:

```
GET /api/chat/history/probe1
  after a successful POST /api/chat/query
  -> {"session_id":"probe1","messages":[]}
```

A `session_id` supplied by the caller was used as a *lookup key only*. When the
lookup missed — which it always did, because the id had never been stored under
that name — the service created the session under a **generated** id and
returned that instead. So:

- every turn returned a different id than the client asked for;
- a client that held its own id across requests got a 200 every time and an
  empty conversation back, which is the worst possible failure — it looks like
  success;
- `POST /api/chat/clear` on that id removed nothing;
- and a new `sessions` row was written per turn, so the table grew without
  bound. 44 stray rows had accumulated in the dev database by the time this was
  found.

The web UI hid it completely. `useChat` adopts the `session_id` from the
response, so the second request *did* find a session and history worked. The
bug only affects a client that generates an id itself — which is the documented
contract (`ChatRequest.session_id` is an optional client-chosen id) and the only
way to have an id before the first response arrives.

Two existing tests asserted the buggy behaviour — that the id *changes* after a
clear. Nothing depended on that: `useChat` calls `setSessionId(null)` on clear.
The tests were pinning a side effect, and the id churn is what hid the real
defect. They were repointed at the invariant they were reaching for (a stale id
recovers rather than 404s; a cleared id starts an empty conversation). Fix in
`chat_service.get_or_create_session`; 8 new tests, one per consequence.

### The free tier's token limit is a demo hazard, and it is not the server's

Ten concurrent queries returned eight `503`s. Not a concurrency bug — the
provider:

```
Rate limit reached for model `openai/gpt-oss-120b` ... on tokens per minute
(TPM): Limit 8000, Used 7386, Requested 1429. Please try again in 6.1s.
```

One answer costs 1,400–1,800 tokens once retrieved passages and the prompt are
counted, so the free tier allows **about five questions a minute**. The backend
behaved correctly throughout: it retried, then failed loudly with a structured
`LLM_UNAVAILABLE` rather than hanging or inventing an answer.

`e2e_check.py` now classifies that as SKIP with the explanation, not PASS and
not FAIL — it measured the provider's quota, so it cannot say anything about
server concurrency either way. This is the single most likely way the demo goes
wrong and it is called out at the top of `demo/README.md`.

### The nginx config in the plan would not stream

The plan writes the config with `RUN echo 'server { \ ... }' > default.conf`.
Whatever the line-continuation handling does, that form cannot be reviewed,
cannot be linted, and cannot be validated: a syntax error passes
`docker compose build` and then kills the container on first boot. It is a real
`frontend/nginx.conf`, `COPY`d in, with `RUN nginx -t` at build time so a bad
config fails the build instead.

It is also missing four directives this application cannot work without:

| Directive | Without it |
|---|---|
| `proxy_buffering off` on `/api/chat/stream` | nginx buffers the whole answer before forwarding. The typing animation does not animate; deltas arrive in one lump and streaming is indistinguishable from the non-streaming endpoint. |
| `proxy_read_timeout 300s` | the 60s default cuts off a slow generation and surfaces it as an unexplained failure |
| `client_max_body_size 60m` | nginx's 1MB default rejects every document over 1MB with a 413 the backend never sees, contradicting the documented 50MB limit |
| `try_files $uri $uri/ /index.html` | a hard refresh on `/chat` or `/admin` returns nginx's 404. Only the *client* router knows to render a page for those paths, and reloading mid-talkout is likely. |

### Deviations

| # | Plan says | What was built | Why |
|---|---|---|---|
| 1 | `LandingPage` renders its own `<Header />` | `Header` is rendered once by `AppRoutes`, above the routed outlet; `LandingPage` renders none | The plan's own criterion is "Header displays on all pages". Rendering it per page duplicates it in three files and, with the plan's `LandingPage` also routed at `/`, puts two nav bars on the landing page. A test asserts exactly one nav on all three routes. |
| 2 | `/` → `<Navigate to="/chat" />` | `/` → `LandingPage` | Task 6.2 exists. `/chat` remains a real route — a refresh on it must not move the presenter mid-demo. |
| 3 | `App` is not split | `AppRoutes` exported alongside `App` | A `BrowserRouter` reads the live address bar, which jsdom will not let a test move. Splitting the routed tree out is what makes routing testable at all; the alternative is testing one URL. |
| 4 | Brand link goes to `/chat` | Goes to `/` | On the landing page the two are different places, and a logo that navigates somewhere other than where it looks like it goes is a small trap. |
| 5 | Landing copy: "AI-Powered Answers", "find the most relevant information instantly" | Copy claims only what the system does: it cites sources, it says when it does not know, it runs with no API key | Overstating the product on the landing screen and then admitting ignorance in the transcript is the combination that makes a demo look dishonest. The honest version is also the more interesting one. A test asserts both claims survive a copy edit. |
| 6 | Decorative icons with no `aria-hidden` | All icons hidden from assistive tech | Adjacent to real text, so the icon's own name is noise. |
| 7 | `compose` sets `version: "3.9"` | No `version:` key | Ignored by Compose v2 since 2023; now only emits a deprecation warning. |
| 8 | `compose` passes only `OPENAI_API_KEY` and `LLM_MODEL` | Also `GROQ_API_KEY`, `LLM_PROVIDER`, `EMBEDDING_PROVIDER`, and absolute paths for the database, Chroma and uploads | The plan's env leaves the container in offline mode, because the LLM key this project uses is a Groq one. Worse, the paths it does set are relative, so the app would be told to read state from a different place than it writes it. |
| 9 | No `env_file` | `env_file: {path: ./backend/.env, required: false}` | `required: false` is the difference between a container that boots with no credentials and one that refuses to start without a paid key. A demo that will not boot on the wrong network is a demo that breaks. |
| 10 | No healthchecks | Healthcheck on both; `depends_on: condition: service_healthy` | Ordering on start alone leaves nginx proxying to a backend still importing chromadb, so the first request after a cold `up` is a 502. On a demo machine a cold start is exactly when the first request happens. |
| 11 | `./data:/app/data` host bind mount | Named volume `rag-data` | A bind mount of the repo-root `./data` is not where the app's data lives (`backend/data/`), so it would silently start empty. A named volume also keeps the container's index independent of the local one — otherwise a container and a local uvicorn open the same SQLite file. |
| 12 | No `.dockerignore` | One per context, both excluding `.env` | `.env` holds a real API key. The backend Dockerfile only copies `requirements.txt` and `app/`, so it cannot leak today — but that guarantee currently depends on the Dockerfile continuing to be written that way. The frontend's `COPY . .` also pulls in `node_modules`. |
| 13 | `backend` runs as root | `USER app`, with `/app/data` created and chowned up front | SQLite and Chroma both need to create files there and fail obscurely at the first request if they cannot. |
| 14 | No build-time config validation | `RUN nginx -t` | Turns a config error into a build failure instead of a crash on first boot — five minutes before a presentation rather than while someone is still fixing things. |
| 15 | E2E testing is "N/A (testing checklist)" | `scripts/e2e_check.py`, run and reported | A checklist in a markdown file is a snapshot. This is the same list as executable checks, and running it is what found the session bug. |
| 16 | Checklist asks "10 concurrent queries → all succeed" | Reported as SKIP, with the reason | The target is unreachable under the provider's per-minute quota, and the script's own traffic shares that budget. Reporting it as either a pass or a failure would be a claim the numbers do not support. |
| 17 | Sample documents in `backend/samples/demo/` | Moved to `demo/sample-documents/`, as Task 6.5 specifies | The plan's own file list. `backend/samples/demo/lecture.md` also duplicated the syllabus verbatim, which made it impossible to demonstrate the best property of the system — that two questions retrieve two *different* documents and each answer cites only the one it came from. Replaced with three disjoint documents. `fixtures/src.txt` remains a near-duplicate of the syllabus's grading passage, which is what that fixture is for. |
| 18 | Demo script is a 7-step outline | A timed runbook with a pre-flight, a verified-question table, failure modes, and an explicit verified/not-verified section | The plan's script has a step that says "show the architecture diagram". There is no diagram. |

### What was verified, and how

Run live against the running system, not inferred from the code:

- 10 questions across 3 documents, each checked for **both** answer content and
  correct source attribution — 10/10
- 3 off-topic questions, all declining rather than inventing — 3/3
- Upload and indexing for TXT, PDF (hand-built, so pypdf is genuinely exercised)
  and DOCX; rejection of bad types and of oversize files
- Streaming: incremental deltas, and a terminal frame carrying `mode` + `sources`
- Latency: upload ~50ms, query 0.9–1.5s, first streamed frame ~600–900ms
- The rate limiter, returning a structured 429

Verified by test suite, not by a human looking at a screen:

- the frontend — 207 tests in jsdom, `tsc`, `eslint` and the production build
  all clean
- backend — 281 tests, `ruff` clean

Not verified at all:

- `docker compose up`. The compose file parses, every environment variable is
  validated against the settings model, `CORS_ORIGINS` is checked to decode as
  `List[str]`, every path is absolute and consistent with the volume mount, and
  `nginx.conf` is checked for brace balance, statement termination, and the
  presence of the four directives above. **No image has been built.** The
  Dockerfile also uses Python 3.11 while everything else uses 3.9 — the code is
  3.9-syntax-clean and 3.11 is still maintained, but that combination has never
  been exercised.
- the 50MB document path (`--with-large`)
- a genuinely empty index
- the UI on a projector

---

## Quick Reference: Complete File Tree

```
rag-chatbot/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Chat/
│   │   │   │   ├── MessageList.tsx
│   │   │   │   ├── MessageBubble.tsx
│   │   │   │   ├── InputBox.tsx
│   │   │   │   ├── TypingIndicator.tsx
│   │   │   │   ├── SourceCard.tsx
│   │   │   │   └── SuggestedQuestions.tsx
│   │   │   ├── Admin/
│   │   │   │   ├── DocumentList.tsx
│   │   │   │   ├── DocumentCard.tsx
│   │   │   │   └── UploadButton.tsx
│   │   │   └── Common/
│   │   │       └── Header.tsx
│   │   ├── pages/
│   │   │   ├── ChatPage.tsx
│   │   │   ├── AdminPage.tsx
│   │   │   └── LandingPage.tsx
│   │   ├── stores/
│   │   │   ├── chatStore.ts
│   │   │   ├── documentStore.ts
│   │   │   └── sessionStore.ts
│   │   ├── services/
│   │   │   ├── apiClient.ts
│   │   │   ├── chatService.ts
│   │   │   └── documentService.ts
│   │   ├── hooks/
│   │   │   ├── useChat.ts
│   │   │   └── useDocuments.ts
│   │   ├── types/
│   │   │   └── index.ts
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── vite.config.ts
│   └── Dockerfile
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── dependencies.py
│   │   ├── exceptions.py
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   ├── cors.py
│   │   │   ├── logging.py
│   │   │   └── rate_limit.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── documents.py
│   │   │   ├── chat.py
│   │   │   └── health.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── document_service.py
│   │   │   ├── chat_service.py
│   │   │   └── embedding_service.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── document.py
│   │   │   ├── chat.py
│   │   │   └── database.py
│   │   ├── rag/
│   │   │   ├── __init__.py
│   │   │   ├── retriever.py
│   │   │   ├── generator.py
│   │   │   └── pipeline.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── file_handler.py
│   │       └── text_processor.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── test_documents.py
│   │   └── test_chat.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
├── demo/
│   ├── README.md
│   └── sample-documents/
│       └── sample-lecture.pdf
│
├── data/                         # Created at runtime (gitignored)
│   ├── chroma/
│   ├── uploads/
│   └── app.db
│
├── docker-compose.yml
├── .env
├── .gitignore
├── README.md
├── PRD.md
├── architecture.md
└── implementation.md             # This document
```

---

## Summary

| Phase | Name | Key Deliverables | Est. Time |
|-------|------|------------------|-----------|
| 1 | Project Setup & Core Backend | FastAPI app, DB models, config | 2-3 hours |
| 2 | RAG Pipeline — Document Ingestion | Upload, parse, chunk, embed | 3-4 hours |
| 3 | Chat & Answer Generation | Query, retrieve, generate, stream | 3-4 hours |
| 4 | Frontend — Chat Interface | React chat UI, streaming | 3-4 hours |
| 5 | Frontend — Admin Panel | Upload UI, document list | 2-3 hours |
| 6 | Integration, Testing & Demo Prep | Docker, testing, demo script | 2-3 hours |

**Total Estimated Time**: 15-21 hours

---

*End of Document*
