# Architecture Document
## RAG Chatbot for Class Demo

---

| Field | Details |
|-------|---------|
| **Document Title** | System Architecture |
| **Version** | 1.0 |
| **Date** | 2026-09-27 |
| **Status** | Draft |
| **Parent Document** | [PRD.md](./PRD.md) |

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [System Context Diagram](#2-system-context-diagram)
3. [Component Architecture](#3-component-architecture)
4. [Data Flow Diagrams](#4-data-flow-diagrams)
5. [API Design](#5-api-design)
6. [Data Models](#6-data-models)
7. [Technology Stack](#7-technology-stack)
8. [Deployment Architecture](#8-deployment-architecture)
9. [Security Architecture](#9-security-architecture)
10. [Error Handling & Resilience](#10-error-handling--resilience)
11. [Performance Considerations](#11-performance-considerations)
12. [Development Workflow](#12-development-workflow)

---

## 1. Architecture Overview

### 1.1 Architectural Style

The system follows a **modular monolith** architecture with clear separation of concerns. This approach is chosen because:

- **Simplicity**: Easy to develop, deploy, and debug for a class demo
- **Low operational overhead**: Single backend service reduces complexity
- **Fast iteration**: Components can be swapped independently (e.g., LLM provider)
- **Demo-friendly**: Minimal infrastructure requirements

### 1.2 Design Principles

| Principle | Description |
|-----------|-------------|
| **Separation of Concerns** | Each layer has a single, well-defined responsibility |
| **Modularity** | RAG pipeline components are pluggable and interchangeable |
| **Statelessness** | API is stateless; conversation history managed client-side or in-memory |
| **Graceful Degradation** | System continues to function (with reduced capability) if external services fail |
| **Demo-Optimized** | Prioritizes reliability and visual clarity over scalability |

### 1.3 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │   Chat UI        │  │   Admin Panel    │  │   Landing Page   │  │
│  │   (React)        │  │   (React)        │  │   (React)        │  │
│  └────────┬─────────┘  └────────┬─────────┘  └──────────────────┘  │
│           │                     │                                    │
│           └──────────┬──────────┘                                    │
│                      │ HTTP/REST                                     │
└──────────────────────┼──────────────────────────────────────────────┘
                       │
┌──────────────────────┼──────────────────────────────────────────────┐
│                 API GATEWAY LAYER                                   │
│  ┌───────────────────▼───────────────────────────────────────────┐  │
│  │              FastAPI Application Server                        │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │  │
│  │  │ Auth        │  │ Rate        │  │ Request Validation  │   │  │
│  │  │ Middleware  │  │ Limiter     │  │ & Serialization     │   │  │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘   │  │
│  └───────────────────────┬───────────────────────────────────────┘  │
└──────────────────────────┼──────────────────────────────────────────┘
                           │
┌──────────────────────────┼──────────────────────────────────────────┐
│                   SERVICE LAYER                                     │
│  ┌───────────────────────▼───────────────────────────────────────┐  │
│  │                                                             │  │
│  │  ┌─────────────────┐    ┌──────────────────────────────┐   │  │
│  │  │ Document        │    │ Chat                          │   │  │
│  │  │ Service         │    │ Service                       │   │  │
│  │  │                 │    │                               │   │  │
│  │  │ - Upload        │    │ - Query Processing            │   │  │
│  │  │ - Parse         │    │ - Context Assembly            │   │  │
│  │  │ - Chunk         │    │ - LLM Orchestration           │   │  │
│  │  │ - Embed         │    │ - Response Formatting         │   │  │
│  │  │ - Manage        │    │ - Session Management          │   │  │
│  │  └────────┬────────┘    └───────────────┬──────────────┘   │  │
│  │           │                             │                   │  │
│  └───────────┼─────────────────────────────┼───────────────────┘  │
│              │                             │                       │
└──────────────┼─────────────────────────────┼───────────────────────┘
               │                             │
┌──────────────┼─────────────────────────────┼───────────────────────┐
│              │        DATA LAYER            │                       │
│  ┌───────────▼──────────┐  ┌───────────────▼───────────────────┐  │
│  │   Vector Store       │  │   Document Store                  │  │
│  │   (Chroma)           │  │   (Local FS / SQLite)             │  │
│  │                      │  │                                   │  │
│  │  - Embeddings        │  │  - Raw files                      │  │
│  │  - Metadata          │  │  - Parsed text                    │  │
│  │  - Similarity Search │  │  - Chunk mappings                 │  │
│  └──────────────────────┘  └───────────────────────────────────┘  │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────┼──────────────────────────────────────────┐
│              EXTERNAL SERVICES LAYER                                │
│  ┌───────────────────────▼───────────────────────────────────────┐  │
│  │                                                             │  │
│  │  ┌──────────────────┐    ┌──────────────────────────────┐   │  │
│  │  │ Embedding Model  │    │ LLM Service                   │   │  │
│  │  │ (OpenAI / Local) │    │ (OpenAI / Claude / Local)     │   │  │
│  │  └──────────────────┘    └──────────────────────────────┘   │  │
│  │                                                             │  │
│  └─────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────┘
```

---

## 2. System Context Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        RAG CHATBOT SYSTEM                           │
│                                                                     │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐    │
│   │ Instructor  │  │  Student    │  │  External Services      │    │
│   │             │  │             │  │                         │    │
│   │ - Uploads   │  │ - Asks      │  │ - OpenAI API            │    │
│   │   documents │  │   questions │  │ - Anthropic API         │    │
│   │ - Manages   │  │ - Views     │  │ - Embedding Service     │    │
│   │   content   │  │   answers   │  │                         │    │
│   │ - Demos     │  │ - Cites     │  │                         │    │
│   │   chatbot   │  │   sources   │  │                         │    │
│   └──────┬──────┘  └──────┬──────┘  └───────────┬─────────────┘    │
│          │                │                      │                  │
│          └────────────────┼──────────────────────┘                  │
│                           │                                         │
│                    ┌──────▼──────┐                                  │
│                    │   System    │                                  │
│                    │   Boundary  │                                  │
│                    └─────────────┘                                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### External Dependencies

| Dependency | Purpose | Required | Fallback |
|------------|---------|----------|----------|
| OpenAI API | LLM inference | Yes | Local LLM (Ollama) |
| OpenAI Embeddings | Text embedding | No | Local hashed embedder (built in) |
| Chroma DB | Vector storage | Yes | In-memory (ephemeral) |

---

## 3. Component Architecture

### 3.1 Frontend Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    App Shell                             │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │   │
│  │  │   Header    │  │   Router    │  │  Theme Provider │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│  ┌───────────────────────────▼───────────────────────────────┐ │
│  │                      Pages                                 │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  │ │
│  │  │  ChatPage    │  │  AdminPage   │  │  LandingPage   │  │ │
│  │  │              │  │              │  │                │  │ │
│  │  │ - MessageList│  │ - DocList    │  │ - Welcome      │  │ │
│  │  │ - InputBox   │  │ - UploadBtn  │  │ - QuickStart   │  │ │
│  │  │ - Suggestions│  │ - DeleteBtn  │  │ - About        │  │ │
│  │  └──────────────┘  └──────────────┘  └────────────────┘  │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                  │
│  ┌───────────────────────────▼───────────────────────────────┐ │
│  │                   Shared Components                        │ │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────┐ │ │
│  │  │ MessageBubble│ │ TypingIndicator│ │ SourceCard │ │ Spinner│ │ │
│  │  └────────────┘ └────────────┘ └────────────┘ └────────┘ │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                  │
│  ┌───────────────────────────▼───────────────────────────────┐ │
│  │                    State Management                        │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │  React Context / Zustand                              │ │ │
│  │  │  - chatStore: messages, isLoading, error              │ │ │
│  │  │  - docStore: documents, uploadProgress                │ │ │
│  │  │  - sessionStore: sessionId, conversationHistory       │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                  │
│  ┌───────────────────────────▼───────────────────────────────┐ │
│  │                    API Client Layer                        │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │  Axios / Fetch Wrapper                                 │ │ │
│  │  │  - Base URL configuration                             │ │ │
│  │  │  - Request/Response interceptors                      │ │ │
│  │  │  - Error handling                                     │ │ │
│  │  │  - Timeout management                                 │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Backend Components

```
┌─────────────────────────────────────────────────────────────────┐
│                     BACKEND (FastAPI)                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   API Routes Layer                       │   │
│  │                                                         │   │
│  │  /api/documents        /api/chat           /api/health  │   │
│  │  ├─ POST /upload       ├─ POST /query      ├─ GET /     │   │
│  │  ├─ GET  /list         ├─ POST /stream     └─ GET /ready│   │
│  │  ├─ GET  /{id}         └─ POST /clear                   │   │
│  │  └─ DELETE /{id}                                       │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│  ┌───────────────────────────▼───────────────────────────────┐ │
│  │                   Service Layer                            │ │
│  │                                                           │ │
│  │  ┌─────────────────────────────────────────────────────┐ │ │
│  │  │ Document Service                                     │ │ │
│  │  │                                                     │ │ │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │ │ │
│  │  │  │ FileHandler  │  │ TextExtractor│  │ Chunker   │ │ │ │
│  │  │  │              │  │              │  │           │ │ │ │
│  │  │  │ - Validate   │  │ - PDF parse  │  │ - Split   │ │ │ │
│  │  │  │ - Store raw  │  │ - DOCX parse │  │ - Overlap │ │ │ │
│  │  │  │ - Get metadata│ │ - TXT parse  │  │ - Size    │ │ │ │
│  │  │  └──────────────┘  └──────────────┘  └───────────┘ │ │ │
│  │  │                                                     │ │ │
│  │  │  ┌──────────────┐  ┌──────────────┐                │ │ │
│  │  │  │ Embedder     │  │ VectorStore  │                │ │ │
│  │  │  │              │  │              │                │ │ │
│  │  │  │ - Generate   │  │ - Upsert     │                │ │ │
│  │  │  │ - Batch      │  │ - Search     │                │ │ │
│  │  │  │ - Cache      │  │ - Delete     │                │ │ │
│  │  │  └──────────────┘  └──────────────┘                │ │ │
│  │  └─────────────────────────────────────────────────────┘ │ │
│  │                                                           │ │
│  │  ┌─────────────────────────────────────────────────────┐ │ │
│  │  │ Chat Service                                        │ │ │
│  │  │                                                     │ │ │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌───────────┐ │ │ │
│  │  │  │ QueryProc    │  │ ContextAsm   │  │ LLMOrch   │ │ │ │
│  │  │  │              │  │              │  │           │ │ │ │
│  │  │  │ - Embed      │  │ - Assemble   │  │ - Call    │ │ │ │
│  │  │  │ - Retrieve   │  │ - Format     │  │ - Stream  │ │ │ │
│  │  │  │ - Rerank     │  │ - Truncate   │  │ - Parse   │ │ │ │
│  │  │  └──────────────┘  └──────────────┘  └───────────┘ │ │ │
│  │  │                                                     │ │ │
│  │  │  ┌──────────────┐  ┌──────────────┐                │ │ │
│  │  │  │ SessionMgr   │  │ PromptTempl  │                │ │ │
│  │  │  │              │  │              │                │ │ │
│  │  │  │ - History    │  │ - System     │                │ │ │
│  │  │  │ - Context    │  │ - User       │                │ │ │
│  │  │  │ - Clear      │  │ - Few-shot   │                │ │ │
│  │  │  └──────────────┘  └──────────────┘                │ │ │
│  │  └─────────────────────────────────────────────────────┘ │ │
│  │                                                           │ │
│  └───────────────────────────────────────────────────────────┘ │
│                              │                                  │
│  ┌───────────────────────────▼───────────────────────────────┐ │
│  │                   Infrastructure Layer                     │ │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────┐ │ │
│  │  │ Config     │ │ Logger     │ │ Exception  │ │ Cache  │ │ │
│  │  │ Manager    │ │            │ │ Handler    │ │        │ │ │
│  │  └────────────┘ └────────────┘ └────────────┘ └────────┘ │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Data Flow Diagrams

### 4.1 Document Ingestion Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│          │     │          │     │          │     │          │     │          │
│ Instructor│     │ Frontend │     │ Backend  │     │ Embedder │     │ Vector   │
│          │     │          │     │          │     │          │     │ Store    │
│          │     │          │     │          │     │          │     │          │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │                │
     │  1. Upload PDF │                │                │                │
     │───────────────>│                │                │                │
     │                │                │                │                │
     │                │  2. POST /upload│                │                │
     │                │  (multipart)   │                │                │
     │                │───────────────>│                │                │
     │                │                │                │                │
     │                │                │  3. Validate   │                │
     │                │                │     file       │                │
     │                │                │                │                │
     │                │                │  4. Extract    │                │
     │                │                │     text       │                │
     │                │                │                │                │
     │                │                │  5. Chunk text │                │
     │                │                │     (500 tokens)│               │
     │                │                │                │                │
     │                │                │  6. Generate   │                │
     │                │                │     embeddings │                │
     │                │                │───────────────>│                │
     │                │                │                │                │
     │                │                │  7. Return     │                │
     │                │                │     vectors    │                │
     │                │                │<───────────────│                │
     │                │                │                │                │
     │                │                │  8. Store      │                │
     │                │                │     vectors +  │                │
     │                │                │     metadata   │                │
     │                │                │─────────────────────────────── >│
     │                │                │                │                │
     │                │                │  9. Confirm    │                │
     │                │                │     stored     │                │
     │                │                │<─────────────────────────────── │
     │                │                │                │                │
     │                │  10. Success   │                │                │
     │                │     response   │                │                │
     │                │<───────────────│                │                │
     │                │                │                │                │
     │  11. Show in   │                │                │                │
     │      doc list  │                │                │                │
     │<───────────────│                │                │                │
     │                │                │                │                │
```

### 4.2 Query Processing Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│          │     │          │     │          │     │          │     │          │
│ Student  │     │ Frontend │     │ Backend  │     │ Vector   │     │ LLM      │
│          │     │          │     │          │     │ Store    │     │ Service  │
│          │     │          │     │          │     │          │     │          │
└────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘     └────┬─────┘
     │                │                │                │                │
     │  1. Type       │                │                │                │
     │     question   │                │                │                │
     │───────────────>│                │                │                │
     │                │                │                │                │
     │                │  2. POST /query│                │                │
     │                │───────────────>│                │                │
     │                │                │                │                │
     │                │                │  3. Embed      │                │
     │                │                │     question   │                │
     │                │                │                │                │
     │                │                │  4. Similarity │                │
     │                │                │     search     │                │
     │                │                │───────────────>│                │
     │                │                │                │                │
     │                │                │  5. Return     │                │
     │                │                │     top-K      │                │
     │                │                │     chunks     │                │
     │                │                │<───────────────│                │
     │                │                │                │                │
     │                │                │  6. Assemble   │                │
     │                │                │     context    │                │
     │                │                │                │                │
     │                │                │  7. Build      │                │
     │                │                │     prompt     │                │
     │                │                │                │                │
     │                │                │  8. Call LLM   │                │
     │                │                │─────────────────────────────── >│
     │                │                │                │                │
     │                │                │                │                │  9. Generate
     │                │                │                │                │     response
     │                │                │                │                │
     │                │                │  10. Return    │                │
     │                │                │      answer    │                │
     │                │                │<─────────────────────────────── │
     │                │                │                │                │
     │                │  11. Stream    │                │                │
     │                │      response  │                │                │
     │                │<───────────────│                │                │
     │                │                │                │                │
     │  12. Display   │                │                │                │
     │      answer +  │                │                │                │
     │      sources   │                │                │                │
     │<───────────────│                │                │                │
     │                │                │                │                │
```

### 4.3 RAG Pipeline Detailed Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        RAG PIPELINE                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    INDEXING PHASE                                │   │
│  │                                                                  │   │
│  │  ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐   ┌──────┐ │   │
│  │  │ Raw    │──▶│Parsed  │──▶│Chunks  │──▶│Embeddings│──▶│Vector│ │   │
│  │  │Document│   │Text    │   │        │   │         │   │Store │ │   │
│  │  └────────┘   └────────┘   └────────┘   └────────┘   └──────┘ │   │
│  │                                                                  │   │
│  │  PDF/DOCX    Plain text    500-token    1536-dim      Chroma  │   │
│  │  TXT/MD      w/ metadata   w/ overlap   vectors        DB      │   │
│  │                                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    RETRIEVAL PHASE                               │   │
│  │                                                                  │   │
│  │  ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐   ┌──────┐ │   │
│  │  │ User   │──▶│ Query  │──▶│Semantic │──▶│ Rerank │──▶│ Top-K│ │   │
│  │  │Question│   │Embed   │   │Search  │   │        │   │Context│ │   │
│  │  └────────┘   └────────┘   └────────┘   └────────┘   └──────┘ │   │
│  │                                                                  │   │
│  │  "What is   1536-dim    Cosine      Optional     3-5 most  │   │
│  │  RAG?"     vector      similarity   scoring      relevant  │   │
│  │                                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    GENERATION PHASE                              │   │
│  │                                                                  │   │
│  │  ┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐   ┌──────┐ │   │
│  │  │Assembled│──▶│ Prompt │──▶│  LLM   │──▶│Parsed  │──▶│Response│ │
│  │  │Context  │   │Template│   │ Call   │   │Response│   │+ Sources│ │
│  │  └────────┘   └────────┘   └────────┘   └────────┘   └──────┘ │   │
│  │                                                                  │   │
│  │  Retrieved   System +      big pickle/ Extract     Answer +  │   │
│  │  chunks +    User prompt   Claude     text + refs   citations │   │
│  │  history                                                     │   │
│  │                                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.4 Local Embedder: Division of Labour

`EMBEDDING_PROVIDER=auto` falls back to a hashed bag-of-words
(`LocalHashEmbedder`) when no usable OpenAI key is present, so the demo runs
with no credentials. It is a **high-recall lexical net, not a relevance
filter**, and the pipeline relies on that division:

- **Retrieval** guarantees only that a word present in a document is *findable*
  by that word. It does not separate an in-domain question from an unrelated
  one — after L2 normalisation against a 160-feature chunk, both are dominated
  by collision noise, and an off-topic question like "What is the weather like
  today?" still scores ~0.2.
- **Sentence scoring** in the offline generator (`_overlap`, with light
  stemming) is what rejects an off-topic question, returning the "I don't have
  information about that" fallback. That is why the fallback is trustworthy
  despite the vector's low discrimination.

Unigrams and bigrams are hashed into a fixed-width vector with TF sublinear
weighting (`1 + log n`), then L2-normalised so cosine similarity is a plain dot
product. Accumulation is **unsigned**. Signed hashing is the usual advice to
reduce collision bias, and it was tried, but it has a worse failure mode here:
two features landing in the same bucket with equal counts and opposite signs
cancel *exactly*, so a word in the document contributes nothing to a query for
that word — invisible, not merely noisy. In a realistic 160-feature syllabus
chunk at 512 dimensions, 24 buckets collided and 9 cancelled outright;
"homework" was annihilated by "trees", and "What does homework contribute?"
retrieved nothing from the only document stating the homework weighting.
Widening the vector reduces the rate but does not remove it — a term in this
corpus still cancelled at 8192 dimensions.

Unsigned accumulation makes presence *sufficient*: if `t` occurs in the document
its bucket holds a positive weight, so the dot product with the single-feature
query vector for `t` is positive by construction. Collisions can only add to a
match, never erase one. The cost is that unrelated documents share some mass
through collisions, which is the trade the division of labour above already
assumes. `tests/test_embedding.py` pins the invariant and the counterfactual, so
the sign step cannot be reintroduced unnoticed.

`LOCAL_EMBEDDING_DIM` is 2048: enough that collisions are rare for realistic
chunk sizes, at 4× the floats of 512 — irrelevant at this scale.

---

## 5. API Design

### 5.1 REST API Endpoints

#### Document Management

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| `POST` | `/api/documents/upload` | Upload a new document | `multipart/form-data` (file) | `DocumentResponse` |
| `GET` | `/api/documents` | List all documents | — | `List[DocumentResponse]` |
| `GET` | `/api/documents/{id}` | Get document details | — | `DocumentResponse` |
| `DELETE` | `/api/documents/{id}` | Delete a document and its embeddings | — | `{ "status": "deleted" }` |

#### Chat

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| `POST` | `/api/chat/query` | Submit a question and get an answer | `ChatRequest` | `ChatResponse` |
| `POST` | `/api/chat/stream` | Stream a response (SSE) | `ChatRequest` | `text/event-stream` |
| `POST` | `/api/chat/clear` | Clear conversation history | `{ "session_id": "..." }` | `{ "status": "cleared" }` |
| `GET` | `/api/chat/history/{session_id}` | Replay a conversation's messages | — | `ChatHistoryResponse` |

`/api/chat/clear` deletes the session row, so the id is dead afterwards. A
subsequent request that reuses that id transparently starts a new session
rather than returning 404, so a stale id is never a dead end.

#### System

| Method | Endpoint | Description | Request Body | Response |
|--------|----------|-------------|--------------|----------|
| `GET` | `/api/health` | Health check | — | `{ "status": "healthy" }` |
| `GET` | `/api/health/ready` | Readiness probe | — | `{ "ready": true/false }` |

### 5.2 Request/Response Schemas

#### Upload Document

```http
POST /api/documents/upload
Content-Type: multipart/form-data

file: <binary>
```

**Response (201 Created)**:
```json
{
  "id": "doc_abc123",
  "filename": "lecture_01.pdf",
  "file_type": "pdf",
  "file_size": 2457600,
  "chunk_count": 42,
  "status": "processed",
  "created_at": "2026-09-27T10:30:00Z"
}
```

#### List Documents

```http
GET /api/documents
```

**Response (200 OK)**:
```json
{
  "documents": [
    {
      "id": "doc_abc123",
      "filename": "lecture_01.pdf",
      "file_type": "pdf",
      "file_size": 2457600,
      "chunk_count": 42,
      "status": "processed",
      "created_at": "2026-09-27T10:30:00Z"
    },
    {
      "id": "doc_def456",
      "filename": "notes.txt",
      "file_type": "txt",
      "file_size": 15360,
      "chunk_count": 8,
      "status": "processed",
      "created_at": "2026-09-27T10:35:00Z"
    }
  ],
  "total": 2
}
```

#### Chat Query

```http
POST /api/chat/query
Content-Type: application/json

{
  "question": "What is the main topic of lecture 1?",
  "session_id": "sess_xyz789",
  "include_sources": true
}
```

**Response (200 OK)**:
```json
{
  "answer": "The main topic of lecture 1 is Introduction to Machine Learning. The lecture covers supervised learning, unsupervised learning, and reinforcement learning paradigms...",
  "sources": [
    {
      "document_id": "doc_abc123",
      "filename": "lecture_01.pdf",
      "chunk_index": 0,
      "excerpt": "Introduction to Machine Learning...",
      "similarity": 0.82
    }
  ],
  "session_id": "sess_xyz789",
  "processing_time_ms": 1250,
  "mode": "openai",
  "used_context": true
}
```

- `mode` — `"openai"` when a language model answered, or
  `"offline-extractive"` when no usable API key was available and the answer
  was assembled by quoting retrieved sentences. The offline responder does not
  paraphrase or synthesise, so the client should label it accordingly.
- `used_context` — `false` when retrieval found nothing at all. In that case
  the model was never called and `answer` is the fixed fallback message, which
  is what keeps an empty index from producing a hallucination.
- `sources` is deduplicated to one entry per document, keeping that
  document's highest-scoring chunk.

#### Chat Stream (SSE)

```http
POST /api/chat/stream
Content-Type: application/json

{
  "question": "Explain neural networks",
  "session_id": "sess_xyz789"
}
```

**Response (200 OK, text/event-stream)**:
```
data: {"delta": "Neural", "finish": false}

data: {"delta": " networks", "finish": false}

data: {"delta": " are", "finish": false}

data: {"delta": " computational", "finish": false}

data: {"delta": " models", "finish": false}

data: {"delta": "...", "finish": false}

data: {"delta": "", "finish": true, "sources": [...], "session_id": "sess_xyz789", "mode": "openai"}
```

Sources ride on the terminal frame; render them once `finish` is true. If
generation fails after the response has started, the status code can no longer
be changed, so the failure arrives as a terminal frame with an `error` field:

```
data: {"delta": "", "finish": true, "error": "The language model could not be reached: ..."}
```

The stream response sets `Cache-Control: no-cache` and `X-Accel-Buffering: no`.
The latter matters whenever the app sits behind nginx or a similar proxy,
which will otherwise buffer the whole response and the client sees no
streaming at all.

Streamed turns are persisted exactly like non-streamed ones, so a conversation
can mix both modes and keep its context.

#### Error Response

```json
{
  "error": {
    "code": "DOCUMENT_NOT_FOUND",
    "message": "The requested document does not exist.",
    "details": {
      "document_id": "doc_nonexistent"
    }
  }
}
```

### 5.3 Error Codes

| HTTP Status | Error Code | Description |
|-------------|------------|-------------|
| 400 | `INVALID_FILE_TYPE` | Unsupported file format |
| 400 | `FILE_TOO_LARGE` | File exceeds size limit (50 MB) |
| 400 | `EMPTY_FILE` | Uploaded file has no content |
| 404 | `DOCUMENT_NOT_FOUND` | Document ID does not exist |
| 422 | `PROCESSING_ERROR` | Failed to parse or process document |
| 422 | `VALIDATION_ERROR` | Request body failed validation |
| 429 | `RATE_LIMITED` | Too many requests |
| 500 | `INTERNAL_ERROR` | Unexpected server error |
| 503 | `LLM_UNAVAILABLE` | LLM service is unavailable |
| 503 | `EMBEDDING_UNAVAILABLE` | Embedding service is unavailable |
| 409 | `EMBEDDING_MISMATCH` | Index was built with a different embedding provider; re-upload documents |

`PROCESSING_ERROR` and `VALIDATION_ERROR` are 422. `AppError` subclasses are
re-raised unchanged through every layer that catches a broad exception, so a
documented code and status always survive to the client. Re-wrapping is what
would otherwise turn a 409 `EMBEDDING_MISMATCH` — on `POST /api/documents/upload`
as much as on `/api/chat/query` — into a generic 422 "Unexpected error while
processing the document", hiding both the cause and the remedy stated in its
message.

---

## 6. Data Models

### 6.1 Entity Relationship Diagram

```
┌─────────────────────┐
│     Document        │
├─────────────────────┤
│ id (PK)             │
│ filename            │
│ file_type           │
│ file_size           │
│ file_path           │
│ chunk_count         │
│ status              │
│ created_at          │
│ updated_at          │
└──────────┬──────────┘
           │
           │ 1:N
           │
┌──────────▼──────────┐
│       Chunk         │
├─────────────────────┤
│ id (PK)             │
│ document_id (FK)    │
│ content             │
│ chunk_index         │
│ token_count         │
│ embedding_id        │
│ metadata            │
└──────────┬──────────┘
           │
           │ 1:1
           │
┌──────────▼──────────┐
│     Embedding       │
├─────────────────────┤
│ id (PK)             │
│ chunk_id (FK)       │
│ vector (float[])    │
│ model               │
│ created_at          │
└─────────────────────┘

┌─────────────────────┐
│     Session         │
├─────────────────────┤
│ id (PK)             │
│ created_at          │
│ last_active         │
│ message_count       │
└──────────┬──────────┘
           │
           │ 1:N
           │
┌──────────▼──────────┐
│     Message         │
├─────────────────────┤
│ id (PK)             │
│ session_id (FK)     │
│ role (user/assistant)│
│ content             │
│ sources (JSON)      │
│ created_at          │
└─────────────────────┘
```

### 6.2 Database Schema (SQLite)

```sql
-- Documents table
CREATE TABLE documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    chunk_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chunks table
CREATE TABLE chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    content TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    token_count INTEGER NOT NULL,
    embedding_id TEXT,
    metadata TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

-- Sessions table
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    message_count INTEGER DEFAULT 0
);

-- Messages table
CREATE TABLE messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    sources TEXT,  -- JSON array of source references
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX idx_chunks_document ON chunks(document_id);
CREATE INDEX idx_messages_session ON messages(session_id);
CREATE INDEX idx_messages_created ON messages(created_at);
```

### 6.3 Vector Store Schema (Chroma)

```python
# Collection: "course_documents"

# Document (metadata) schema
{
    "document_id": "doc_abc123",
    "filename": "lecture_01.pdf",
    "file_type": "pdf",
    "chunk_index": 0,
    "page_number": 1,
    "section": "Introduction"
}

# Embedding document schema
{
    "ids": ["chunk_001"],
    "embeddings": [[0.0123, -0.0456, ...]],  # 1536-dim vector
    "documents": ["Introduction to Machine Learning..."],
    "metadatas": [
        {
            "document_id": "doc_abc123",
            "filename": "lecture_01.pdf",
            "chunk_index": 0,
            "page_number": 1
        }
    ]
}
```

---

## 7. Technology Stack

### 7.1 Finalized Stack

| Layer | Technology | Version | Justification |
|-------|-----------|---------|---------------|
| **Frontend** | React + Vite | React 18, Vite 5 | Fast dev, HMR, small bundle |
| **Language** | TypeScript | 5.x | The API contract is the fragile part; types catch drift at build time |
| **UI Components** | Tailwind CSS + typography plugin | 3.x | Rapid styling, responsive; the plugin styles rendered markdown |
| **Markdown** | react-markdown + remark-gfm | 9.x / 4.x | Tables, lists, code in answers |
| **State Management** | Zustand | 5.x | Lightweight, simple API |
| **HTTP Client** | Axios | 1.x | Interceptors, error handling |
| **Streaming** | `fetch` + a hand-written SSE parser | — | `EventSource` cannot POST a JSON body |
| **Frontend Tests** | Vitest + Testing Library | 2.x | Shares Vite's transform pipeline, no extra config |
| **Backend** | Python + FastAPI | Python 3.11, FastAPI 0.110 | Async, auto-docs, type hints |
| **Task Queue** | Celery + Redis | — | Background processing (optional) |
| **Embedding Model** | OpenAI text-embedding-3-small | — | High quality, cost-effective |
| **Vector Database** | Chroma | 0.4.x | Local, persistent, easy to use |
| **LLM** | big pickle | — | Custom model for demo |
| **Document Parsing** | pypdf + python-docx | — | Multi-format support |
| **Tokenization** | tiktoken | 0.5.x | Matches the OpenAI token budget |
| **Orchestration** | Plain Python services | — | No framework needed; keeps deps small |
| **Database** | SQLite | 3.x | Zero-config, file-based |
| **Deployment** | Docker + Docker Compose | — | Reproducible environment |

### 7.2 Alternative Options

| Component | Alternative | When to Use |
|-----------|-------------|-------------|
| LLM | Anthropic Claude 3.5 | Better reasoning, lower hallucination |
| LLM | Ollama (Llama 3) | No internet, no API costs |
| Embeddings | Local hashed bag-of-words (built in) | Zero dependencies, works offline |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 | Better local quality, but pulls in torch (~2GB) |
| Vector DB | Pinecone | Cloud-hosted, scalable |
| Vector DB | FAISS | In-memory, fastest for small datasets |
| Backend | Flask | Simpler, more familiar |
| Frontend | Next.js | SSR, routing, deployment ease |

### 7.3 Dependency Graph

```
┌─────────────────────────────────────────────────────────────────┐
│                     DEPENDENCY GRAPH                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐                                                │
│  │   React     │                                                │
│  │   Frontend  │                                                │
│  └──────┬──────┘                                                │
│         │ uses                                                   │
│         ▼                                                        │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐       │
│  │   Axios     │────▶│  FastAPI    │────▶│  Pydantic   │       │
│  │             │     │  Backend    │     │  Validation │       │
│  └─────────────┘     └──────┬──────┘     └─────────────┘       │
│                            │                                     │
│              ┌─────────────┼─────────────┐                      │
│              │             │             │                       │
│              ▼             ▼             ▼                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  Pipeline   │  │   Chroma    │  │   SQLite    │             │
│  │  Services   │  │             │  │             │             │
│  │             │  │ - Embed     │  │ - Metadata  │             │
│  │ - Parsers   │  │ - Search    │  │ - Sessions  │             │
│  │ - Chunker   │  │ - Store     │  │ - Messages  │             │
│  │ - Prompts   │  └──────┬──────┘  └─────────────┘             │
│  └──────┬──────┘         │                                       │
│         │                ▼                                       │
│         │       ┌──────────────────┐                            │
│         │       │ Embedder         │                            │
│         │       │ (pluggable)      │                            │
│         │       │ - OpenAI         │                            │
│         │       │ - local hash     │                            │
│         │       └──────────────────┘                            │
│         ▼                                                        │
│  ┌─────────────┐                                                │
│  │  OpenAI     │                                                │
│  │  API        │                                                │
│  │             │                                                │
│  │ - big pickle│                                                │
│  └─────────────┘                                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. Deployment Architecture

### 8.1 Local Development

```
┌─────────────────────────────────────────────────────────────────┐
│                    LOCAL DEVELOPMENT                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐              ┌──────────────────┐         │
│  │   Frontend       │              │   Backend        │         │
│  │   (Vite Dev)     │              │   (Uvicorn)      │         │
│  │                  │              │                  │         │
│  │   localhost:5173 │─────────────▶│   localhost:8000 │         │
│  │                  │   CORS       │                  │         │
│  └──────────────────┘              └────────┬─────────┘         │
│                                           │                    │
│                              ┌────────────┼────────────┐       │
│                              │            │            │        │
│                              ▼            ▼            ▼        │
│                       ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│                       │  Chroma  │ │  SQLite  │ │  OpenAI  │   │
│                       │  (local) │ │  (file)  │ │  (cloud) │   │
│                       └──────────┘ └──────────┘ └──────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 Docker Deployment

```
┌─────────────────────────────────────────────────────────────────┐
│                    DOCKER COMPOSE                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    docker-compose.yml                     │  │
│  │                                                          │  │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │  │
│  │  │   frontend  │    │   backend   │    │   chroma    │  │  │
│  │  │   service   │    │   service   │    │   service   │  │  │
│  │  │             │    │             │    │             │  │  │
│  │  │  Port: 3000 │    │  Port: 8000 │    │  Port: 8001 │  │  │
│  │  │  (nginx)    │    │  (uvicorn)  │    │  (chroma)   │  │  │
│  │  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘  │  │
│  │         │                  │                  │         │  │
│  │         └──────────────────┼──────────────────┘         │  │
│  │                            │                            │  │
│  │                   ┌────────▼────────┐                   │  │
│  │                   │   Shared        │                   │  │
│  │                   │   Network       │                   │  │
│  │                   │   (app-network) │                   │  │
│  │                   └─────────────────┘                   │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                               │
│  Volumes:                                                     │
│  - ./data/chroma:/chroma/chroma    (vector store persistence) │
│  - ./data/uploads:/app/uploads     (uploaded files)           │
│  - ./data/sqlite:/app/data         (SQLite database)          │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

### 8.3 Production Deployment (Cloud)

```
┌─────────────────────────────────────────────────────────────────┐
│                    CLOUD DEPLOYMENT                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                      Vercel / Netlify                     │  │
│  │                      (Frontend Hosting)                   │  │
│  │                                                          │  │
│  │   ┌─────────────────────────────────────────────────┐   │  │
│  │   │  React SPA (Static Build)                       │   │  │
│  │   │  - Auto-deploy on git push                      │   │  │
│  │   │  - CDN distribution                             │   │  │
│  │   │  - Custom domain                                │   │  │
│  │   └─────────────────────────────────────────────────┘   │  │
│  └──────────────────────────┬───────────────────────────────┘  │
│                             │                                   │
│                             │ HTTPS                             │
│                             ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   Railway / Render                        │  │
│  │                   (Backend Hosting)                       │  │
│  │                                                          │  │
│  │   ┌─────────────────────────────────────────────────┐   │  │
│  │   │  FastAPI Application                            │   │  │
│  │   │  - Auto-deploy from Docker                       │   │  │
│  │   │  - Health checks                                │   │  │
│  │   │  - Auto-scaling (if needed)                     │   │  │
│  │   └─────────────────────────────────────────────────┘   │  │
│  └──────────────────────────┬───────────────────────────────┘  │
│                             │                                   │
│              ┌──────────────┼──────────────┐                   │
│              │              │              │                    │
│              ▼              ▼              ▼                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   Chroma     │  │   SQLite     │  │   OpenAI     │         │
│  │   (Railway   │  │   (Railway   │  │   API        │         │
│  │    Volume)   │  │    Volume)   │  │   (Cloud)    │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                               │
└───────────────────────────────────────────────────────────────┘
```

### 8.4 Environment Variables

```bash
# .env file

# Application
APP_NAME="RAG Chatbot"
APP_ENV="development"  # development | staging | production
DEBUG=true

# Server
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=["http://localhost:5173"]

# OpenAI -- used for embeddings, and for chat when configured directly
OPENAI_API_KEY=sk-...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
# Endpoint for the embedding client. Blank = api.openai.com.
OPENAI_BASE_URL=

# Groq -- chat completions only
GROQ_API_KEY=gsk-...
GROQ_BASE_URL=https://api.groq.com/openai/v1

# The model that writes the answers. Must be a name the endpoint serves.
LLM_MODEL=openai/gpt-oss-120b

# Embeddings
# auto  -> OpenAI when OPENAI_API_KEY is a real key, else the local embedder
# openai -> force OpenAI (errors if the key is missing)
# local -> force the local embedder (no API key, no torch download)
#
# Pinned to `local` in the shipped .env: a real API key must change the answers
# without invalidating the index. On `auto` the key would switch the vector
# width from 2048 to 1536 and every query would then fail with 409
# EMBEDDING_MISMATCH until all documents were re-uploaded.
EMBEDDING_PROVIDER=local
LOCAL_EMBEDDING_DIM=2048
EMBEDDING_BATCH_SIZE=100
EMBEDDING_CACHE_SIZE=2048

# Vector Store
CHROMA_PERSIST_DIR=./data/chroma
CHROMA_COLLECTION_NAME=course_documents

# Database
DATABASE_URL=sqlite:///./data/app.db
SQL_ECHO=false

# Document Processing
MAX_FILE_SIZE_MB=50
CHUNK_SIZE=500
CHUNK_OVERLAP=50
TOP_K_RETRIEVAL=5
# Cosine distance above which a retrieved chunk is treated as irrelevant.
MAX_RETRIEVAL_DISTANCE=1.0

# LLM Settings
# groq    -> require GROQ_API_KEY (startup error if missing/placeholder)
# openai  -> require OPENAI_API_KEY (same)
# auto    -> whichever usable key is configured, preferring Groq; offline if
#            neither is set
# offline -> force the extractive responder
LLM_PROVIDER=groq
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=1024
LLM_TIMEOUT_SECONDS=30
# Prior turns fed back to the model (user+assistant pairs). The most recent
# N messages are used, not the oldest.
MAX_HISTORY_MESSAGES=10
# Characters of a retrieved chunk shown as a source excerpt.
SOURCE_EXCERPT_CHARS=200
# Sentences the offline responder quotes back, and the minimum lexical overlap
# required for a sentence to be included.
OFFLINE_MAX_SENTENCES=4
OFFLINE_MIN_SIMILARITY=0.02

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=60
```

`LLM_PROVIDER=auto` and `EMBEDDING_PROVIDER=auto` are what keep the demo
usable without credentials. Both fall back to local implementations when
`OPENAI_API_KEY` is absent or still the `.env.example` placeholder. Because the
two fall back independently, a real key switches *both* to OpenAI — and the two
embedding providers produce different vector widths, so an existing index
becomes unqueryable and documents must be re-uploaded. That surfaces as a 409
`EMBEDDING_MISMATCH` rather than silently returning meaningless neighbours.

This is why the shipped `.env` pins `EMBEDDING_PROVIDER=local` rather than
leaving it on `auto`. The failure it avoids is not gradual: `_assert_compatible`
runs in `embed_texts`, so the mismatch breaks the *query* path as well as
uploads, and every chat request 409s until the index is rebuilt. Pinning
embeddings decouples them — a key changes what writes the answers, retrieval
keeps the width it was built with, and the two can be adopted independently.
Switching `EMBEDDING_PROVIDER` to `openai` remains supported and is the right
move when the paraphrase gap in §4.4 is worth re-indexing to close; the
recovery path is §8.5.

### 8.4.1 Two providers, two jobs

Chat completions and embeddings are configured from **separate** key settings,
because they are served by different systems and have different failure modes:

| | Setting | Serves | Provider in use |
|---|---|---|---|
| Answers | `GROQ_API_KEY` + `GROQ_BASE_URL` | chat completions | Groq |
| Retrieval | `EMBEDDING_PROVIDER` + `OPENAI_API_KEY` | embeddings | local hash |

Groq is an inference endpoint and serves no embedding model, so the two cannot
share a key. More importantly the separation means adding an LLM key is a
one-line change that cannot invalidate the index — the failure mode that
`EMBEDDING_PROVIDER=local` already guards against for the `auto` setting.

Both clients are built from the same kwargs helper
(`Settings._client_kwargs`), which omits `base_url` entirely when unset rather
than passing `base_url=""`: the SDK reads an empty base URL as a real origin and
every request then fails with an opaque URL error. "Not configured" has to mean
"argument absent", not "argument empty".

`Settings.llm_endpoint` resolves which API answers, preferring Groq when both
keys are present. `LLM_PROVIDER` overrides it, and an explicit value that cannot
be satisfied raises `LLMUnavailableError` instead of falling through to the other
provider — asking for one provider and being silently served another would make
the `mode` field a lie. The `mode` value is the provider's own name
(`"groq"`, `"openai"`, `"offline-extractive"`), and `ModeBadge` matches offline
by value rather than by "anything that is not `openai`", so a newly added
provider cannot render as a claim that no model was called.

Model names are provider state, not project state, and they rot:
`llama-3.1-8b-instant` and `big-pickle` both 404 today. A 404 surfaces as
`LLM_UNAVAILABLE`, and `GET /models` on the endpoint lists what is actually
available.

### 8.5 Recovering from a width change

The mismatch is only a real constraint while the index holds vectors. Two
independent pieces of state record the width, and the recovery path has to
clear both, or the documented remedy cannot complete:

| State | Where it lives | How it is cleared |
|-------|----------------|-------------------|
| Index-info sidecar | `data/chroma/index_info.json` | Deleted, then rewritten by the next store |
| Collection width | Chroma's own `collections` table | Collection deleted and recreated |

The sidecar is ours to discard. The collection width is not: Chroma fixes it
when the collection is created and exposes no public accessor for it, so it
survives emptying the collection. `store_embeddings` therefore recognises
Chroma's "does not match collection dimensionality" rejection and, **only when
the collection is empty**, rebuilds it and retries once. A populated collection
is never rebuilt — that stays a 409, because it would silently discard indexed
documents.

Without the empty-index exemption the recovery is a deadlock rather than an
annoyance: the error tells the user to "delete the documents and upload them
again", and deleting the last document would still leave a mismatch that
refuses every upload, with no way out but deleting `data/chroma/` by hand.

The admin panel's status card reports the same disagreement *before* it
becomes an upload failure. `GET /api/documents/stats` returns both halves:

| Field | Meaning |
|-------|---------|
| `embedding_model` | what the service would embed with right now |
| `indexed_with` | what the existing index was built with (`null` when empty) |

`SystemStatus.tsx` renders a warning when the two differ, because that state
is otherwise invisible: the app is perfectly healthy, every existing query
works, and the only symptom is that the *next* upload fails with a 409 whose
message mentions two model names the user never chose. A `null` `indexed_with`
is an empty index, not a disagreement, and is not warned about.

---

## 9. Security Architecture

### 9.1 Security Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                    SECURITY LAYERS                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer 1: Transport Security                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  - HTTPS/TLS for all communications                      │   │
│  │  - HSTS headers                                         │   │
│  │  - Secure cookies (if applicable)                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Layer 2: API Security                                          │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  - CORS configuration (whitelist origins)               │   │
│  │  - Rate limiting (per IP / per session)                 │   │
│  │  - Request size limits                                  │   │
│  │  - Input validation (Pydantic models)                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Layer 3: Data Security                                         │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  - No PII storage (demo context)                        │   │
│  │  - File type validation                                 │   │
│  │  - File size limits                                     │   │
│  │  - Secure file storage (permissions)                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Layer 4: External Service Security                              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  - API key management (env vars, never hardcoded)       │   │
│  │  - API key rotation                                     │   │
│  │  - Timeout handling                                     │   │
│  │  - Retry with exponential backoff                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  Layer 5: Application Security                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  - Prompt injection prevention                          │   │
│  │  - Output sanitization                                  │   │
│  │  - Error message sanitization (no stack traces in prod) │   │
│  │  - Logging (no sensitive data in logs)                  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 9.2 File Upload Security

```
┌─────────────────────────────────────────────────────────────────┐
│                    FILE UPLOAD SECURITY                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐                                               │
│  │ Uploaded File│                                               │
│  └──────┬───────┘                                               │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 1. File Type Validation                                   │  │
│  │    - Check MIME type                                      │  │
│  │    - Check file extension                                 │  │
│  │    - Reject: .exe, .bat, .sh, .php, etc.                  │  │
│  │    - Allow: .pdf, .txt, .docx, .md                        │  │
│  └──────────────────────────────────────────────────────────┘  │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 2. File Size Validation                                   │  │
│  │    - Max size: 50 MB                                      │  │
│  │    - Reject if exceeded                                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 3. Content Validation                                     │  │
│  │    - Verify file is not empty                             │  │
│  │    - Verify file is valid format (not corrupted)          │  │
│  │    - Scan for malicious content (basic)                   │  │
│  └──────────────────────────────────────────────────────────┘  │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 4. Secure Storage                                         │  │
│  │    - Store with random filename (no user input)           │  │
│  │    - Restrict file permissions (read-only for app)        │  │
│  │    - Store outside web root                               │  │
│  └──────────────────────────────────────────────────────────┘  │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 5. Processing                                             │  │
│  │    - Parse in isolated environment                        │  │
│  │    - Timeout on parsing (prevent DoS)                     │  │
│  │    - Log processing results                               │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 10. Error Handling & Resilience

### 10.1 Error Handling Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                    ERROR HANDLING STRATEGY                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   Error Categories                        │  │
│  │                                                          │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │  │
│  │  │  Client     │  │  Server     │  │  External   │     │  │
│  │  │  Errors     │  │  Errors     │  │  Service    │     │  │
│  │  │  (4xx)      │  │  (5xx)      │  │  Errors     │     │  │
│  │  │             │  │             │  │             │     │  │
│  │  │ - Invalid   │  │ - Internal  │  │ - OpenAI    │     │  │
│  │  │   input     │  │   error     │  │   API fail  │     │  │
│  │  │ - Not found │  │ - DB error  │  │ - Rate      │     │  │
│  │  │ - File too  │  │ - Vector DB │  │   limited   │     │  │
│  │  │   large     │  │   error     │  │ - Timeout   │     │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                   Handling Strategy                       │  │
│  │                                                          │  │
│  │  1. Validation Errors (400)                              │  │
│  │     → Return descriptive error message                   │  │
│  │     → Log warning                                        │  │
│  │                                                          │  │
│  │  2. Not Found (404)                                      │  │
│  │     → Return "resource not found" message                │  │
│  │     → Log warning                                        │  │
│  │                                                          │  │
│  │  3. Processing Errors (422)                              │  │
│  │     → Return "failed to process" message                 │  │
│  │     → Log error with details                             │  │
│  │                                                          │  │
│  │  4. Rate Limiting (429)                                  │  │
│  │     → Return "too many requests" + retry-after            │  │
│  │     → Log warning                                        │  │
│  │                                                          │  │
│  │  5. External Service Errors (503)                        │  │
│  │     → Return "service temporarily unavailable"           │  │
│  │     → Log error                                          │  │
│  │     → Trigger fallback (if available)                    │  │
│  │                                                          │  │
│  │  6. Internal Errors (500)                                │  │
│  │     → Return generic "internal error" message            │  │
│  │     → Log full stack trace                               │  │
│  │     → Alert (if production)                              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 10.2 Fallback Strategies

```
┌─────────────────────────────────────────────────────────────────┐
│                    FALLBACK STRATEGIES                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  LLM Fallback                                            │  │
│  │                                                          │  │
│  │  Primary: big pickle                                     │  │
│  │     ↓ (if fails)                                         │  │
│  │  Fallback 1: Anthropic Claude 3.5                          │  │
│  │     ↓ (if fails)                                         │  │
│  │  Fallback 2: Local LLM (Ollama + Llama 3)                │  │
│  │     ↓ (if fails)                                         │  │
│  │  Final: "I'm unable to process your request right now." │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Embedding Fallback                                      │  │
│  │                                                          │  │
│  │  Selected by EMBEDDING_PROVIDER at startup:               │  │
│  │                                                          │  │
│  │  "auto"  (default)                                       │  │
│  │     OpenAI text-embedding-3-small if a usable            │  │
│  │     OPENAI_API_KEY is present, else ↓                    │  │
│  │  local  hashed bag-of-words, 2048-dim, no API key         │  │
│  │     ↓ (if that fails)                                    │  │
│  │  Final: "Document processing temporarily unavailable."   │  │
│  │                                                          │  │
│  │  The index records which model built it. Querying it     │  │
│  │  with a different model raises rather than returning     │  │
│  │  meaningless neighbours.                                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Vector Store Fallback                                   │  │
│  │                                                          │  │
│  │  Primary: Chroma (persistent)                            │  │
│  │     ↓ (if fails)                                         │  │
│  │  Fallback: In-memory FAISS                               │  │
│  │     ↓ (if fails)                                         │  │
│  │  Final: "Search functionality temporarily unavailable."  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 10.3 Retry Logic

```python
# Exponential backoff retry configuration

RETRY_CONFIG = {
    "max_retries": 3,
    "base_delay_seconds": 1,
    "max_delay_seconds": 30,
    "exponential_base": 2,
    "retryable_errors": [
        "timeout",
        "rate_limit",
        "service_unavailable",
        "connection_error"
    ]
}

# Retry delays: 1s, 2s, 4s (with jitter)
```

---

## 11. Performance Considerations

### 11.1 Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| Document upload | < 3 seconds | Time to upload and parse |
| Embedding generation | < 5 seconds | Time to embed all chunks |
| Query response | < 5 seconds | Time from question to answer |
| Streaming start | < 1 second | Time to first token |
| Concurrent users | 50 | Simultaneous active sessions |
| Document capacity | 50 MB total | All uploaded documents |

### 11.2 Optimization Strategies

```
┌─────────────────────────────────────────────────────────────────┐
│                    OPTIMIZATION STRATEGIES                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  1. Caching                                              │  │
│  │     - Cache frequent queries (Redis/in-memory)           │  │
│  │     - Cache embeddings for common questions              │  │
│  │     - Cache LLM responses for identical prompts          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  2. Async Processing                                     │  │
│  │     - Process documents in background                    │  │
│  │     - Stream LLM responses (SSE)                         │  │
│  │     - Non-blocking I/O for all external calls            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  3. Batch Operations                                     │  │
│  │     - Batch embedding generation                         │  │
│  │     - Batch document processing                          │  │
│  │     - Reduce API round trips                             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  4. Prompt Optimization                                  │  │
│  │     - Minimize context window usage                     │  │
│  │     - Truncate long contexts                             │  │
│  │     - Use efficient prompt templates                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  5. Frontend Optimization                                │  │
│  │     - Lazy loading of components                         │  │
│  │     - Virtualized message list                           │  │
│  │     - Optimistic UI updates                              │  │
│  │     - Debounced input                                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 11.3 Caching Strategy

```
┌─────────────────────────────────────────────────────────────────┐
│                    CACHING STRATEGY                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Query Cache                                             │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  Key: hash(question + top_chunks)                   │  │  │
│  │  │  Value: { "answer": "...", "sources": [...] }      │  │  │
│  │  │  TTL: 1 hour                                       │  │  │
│  │  │  Max entries: 1000                                  │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Embedding Cache                                         │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  Key: hash(text_chunk)                             │  │  │
│  │  │  Value: [0.0123, -0.0456, ...]                     │  │  │
│  │  │  TTL: 24 hours                                     │  │  │
│  │  │  Storage: In-memory LRU                             │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Document Cache                                          │  │
│  │  ┌────────────────────────────────────────────────────┐  │  │
│  │  │  Key: document_id                                   │  │  │
│  │  │  Value: { "chunks": [...], "metadata": {...} }     │  │  │
│  │  │  TTL: Session duration                              │  │  │
│  │  │  Storage: In-memory                                 │  │  │
│  │  └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 12. Development Workflow

### 12.1 Project Structure

```
rag-chatbot/
├── frontend/                    # React frontend
│   ├── src/
│   │   ├── components/          # Reusable UI components
│   │   │   ├── Chat/
│   │   │   │   ├── MessageList.tsx
│   │   │   │   ├── MessageBubble.tsx
│   │   │   │   ├── InputBox.tsx
│   │   │   │   ├── TypingIndicator.tsx
│   │   │   │   ├── SourceCard.tsx
│   │   │   │   ├── SuggestedQuestions.tsx
│   │   │   │   ├── ModeBadge.tsx
│   │   │   │   └── MarkdownContent.tsx
│   │   │   ├── Admin/
│   │   │   │   ├── DocumentList.tsx
│   │   │   │   ├── DocumentCard.tsx
│   │   │   │   ├── UploadButton.tsx
│   │   │   │   ├── SystemStatus.tsx
│   │   │   │   ├── ConfirmDialog.tsx
│   │   │   │   ├── format.ts              # size/date formatting
│   │   │   │   └── validateFile.ts        # client-side pre-flight
│   │   │   └── Common/
│   │   │       ├── Header.tsx
│   │   │       ├── Spinner.tsx
│   │   │       └── ErrorBoundary.tsx
│   │   ├── pages/               # Page components
│   │   │   ├── ChatPage.tsx
│   │   │   ├── AdminPage.tsx
│   │   │   └── LandingPage.tsx         # Phase 6
│   │   ├── stores/              # State management
│   │   │   ├── chatStore.ts
│   │   │   ├── documentStore.ts
│   │   │   └── sessionStore.ts
│   │   ├── services/            # API clients
│   │   │   ├── apiClient.ts
│   │   │   ├── chatService.ts
│   │   │   ├── documentService.ts
│   │   │   ├── systemService.ts        # /health, /health/ready
│   │   │   └── sse.ts               # SSE frame parser
│   │   ├── hooks/               # Custom hooks
│   │   │   ├── useChat.ts
│   │   │   ├── useChatHistory.ts
│   │   │   ├── useDocuments.ts
│   │   │   └── useSystemStatus.ts
│   │   ├── types/               # TypeScript types
│   │   │   └── index.ts
│   │   ├── utils/               # Utilities
│   │   │   └── helpers.ts
│   │   ├── App.tsx              # Router + shell
│   │   ├── main.tsx
│   │   └── index.css
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   └── vite.config.ts
│
├── backend/                     # FastAPI backend
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # Application entry point
│   │   ├── config.py            # Configuration management
│   │   ├── dependencies.py      # FastAPI dependencies
│   │   ├── exceptions.py        # Custom exceptions
│   │   ├── middleware/          # Middleware
│   │   │   ├── cors.py
│   │   │   ├── rate_limit.py
│   │   │   └── logging.py
│   │   ├── routes/              # API routes
│   │   │   ├── __init__.py
│   │   │   ├── documents.py
│   │   │   ├── chat.py
│   │   │   └── health.py
│   │   ├── services/            # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── document_service.py   # Parsing, chunking, indexing
│   │   │   ├── chat_service.py      # Sessions, history, persistence
│   │   │   └── embedding_service.py # Embeddings + Chroma
│   │   ├── models/              # Data models
│   │   │   ├── __init__.py
│   │   │   ├── document.py
│   │   │   ├── chat.py
│   │   │   ├── database.py
│   │   │   └── schemas.py        # Pydantic request/response models
│   │   ├── rag/                 # RAG pipeline
│   │   │   ├── __init__.py
│   │   │   ├── retriever.py     # Context retrieval
│   │   │   ├── generator.py     # Prompt building + answer generation
│   │   │   └── pipeline.py      # RAG orchestration
│   │   └── utils/               # Utilities
│   │       ├── __init__.py
│   │       ├── file_handler.py
│   │       └── text_processor.py
│   ├── tests/                   # Test files
│   │   ├── test_chat.py
│   │   ├── test_chat_api.py
│   │   ├── test_documents.py
│   │   ├── test_embedding.py
│   │   ├── test_generator.py
│   │   └── conftest.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
│
├── data/                        # Data storage (gitignored)
│   ├── chroma/                  # Vector store
│   ├── uploads/                 # Uploaded files
│   └── app.db                   # SQLite database
│
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example
├── .gitignore
├── README.md
├── PRD.md
└── architecture.md              # This document
```

### 12.2 API Documentation

FastAPI automatically generates interactive API documentation:

| URL | Description |
|-----|-------------|
| `http://localhost:8000/docs` | Swagger UI (interactive) |
| `http://localhost:8000/redoc` | ReDoc (alternative) |
| `http://localhost:8000/openapi.json` | OpenAPI schema |

### 12.3 Development Commands

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev

# Docker (full stack)
docker-compose up --build

# Testing
cd backend
pytest tests/ -v

# Linting
cd backend
ruff check .
cd frontend
npm run lint
```

---

## Appendix A: Sequence Diagrams

### A.1 Document Upload Sequence

```
Instructor          Frontend           Backend           Embedder          VectorStore
    │                  │                  │                  │                  │
    │  Select file     │                  │                  │                  │
    │─────────────────>│                  │                  │                  │
    │                  │                  │                  │                  │
    │                  │  POST /upload    │                  │                  │
    │                  │  (file)          │                  │                  │
    │                  │─────────────────>│                  │                  │
    │                  │                  │                  │                  │
    │                  │                  │  Validate file   │                  │
    │                  │                  │  Extract text    │                  │
    │                  │                  │  Chunk text      │                  │
    │                  │                  │                  │                  │
    │                  │                  │  Generate embeddings                │
    │                  │                  │─────────────────>│                  │
    │                  │                  │                  │                  │
    │                  │                  │  Return vectors  │                  │
    │                  │                  │<─────────────────│                  │
    │                  │                  │                  │                  │
    │                  │                  │  Store vectors                     │
    │                  │                  │──────────────────────────────────── >│
    │                  │                  │                  │                  │
    │                  │                  │  Confirm stored                    │
    │                  │                  │<──────────────────────────────────── │
    │                  │                  │                  │                  │
    │                  │  201 Created    │                  │                  │
    │                  │<─────────────────│                  │                  │
    │                  │                  │                  │                  │
    │  Show success   │                  │                  │                  │
    │<─────────────────│                  │                  │                  │
    │                  │                  │                  │                  │
```

### A.2 Chat Query Sequence

```
Student            Frontend           Backend           VectorStore        LLM
    │                  │                  │                  │                │
    │  Type question   │                  │                  │                │
    │─────────────────>│                  │                  │                │
    │                  │                  │                  │                │
    │                  │  POST /query     │                  │                │
    │                  │  (question)      │                  │                │
    │                  │─────────────────>│                  │                │
    │                  │                  │                  │                │
    │                  │                  │  Embed question  │                │
    │                  │                  │                  │                │
    │                  │                  │  Search similar │                │
    │                  │                  │─────────────────>│                │
    │                  │                  │                  │                │
    │                  │                  │  Return chunks  │                │
    │                  │                  │<─────────────────│                │
    │                  │                  │                  │                │
    │                  │                  │  Assemble context                │
    │                  │                  │  Build prompt   │                │
    │                  │                  │                  │                │
    │                  │                  │  Call LLM       │                │
    │                  │                  │──────────────────────────────── >│
    │                  │                  │                  │                │
    │                  │                  │                  │                │ Generate
    │                  │                  │                  │                │ response
    │                  │                  │                  │                │
    │                  │                  │  Return answer  │                │
    │                  │                  │<──────────────────────────────── │
    │                  │                  │                  │                │
    │                  │  200 OK          │                  │                │
    │                  │  (answer+sources)│                  │                │
    │                  │<─────────────────│                  │                │
    │                  │                  │                  │                │
    │  Display answer │                  │                  │                │
    │  + sources      │                  │                  │                │
    │<─────────────────│                  │                  │                │
    │                  │                  │                  │                │
```

---

## Appendix B: Configuration Files

### B.1 docker-compose.yml

```yaml
version: "3.9"

services:
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:80"
    depends_on:
      - backend
    networks:
      - app-network

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - CHROMA_PERSIST_DIR=/app/data/chroma
      - DATABASE_URL=sqlite:////app/data/app.db
    volumes:
      - ./data/chroma:/app/data/chroma
      - ./data/uploads:/app/data/uploads
      - ./data:/app/data
    depends_on:
      - chroma
    networks:
      - app-network

  chroma:
    image: chromadb/chroma:latest
    ports:
      - "8001:8000"
    volumes:
      - ./data/chroma:/chroma/chroma
    networks:
      - app-network

networks:
  app-network:
    driver: bridge
```

### B.2 Backend Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### B.3 Frontend Dockerfile

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
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

---

*End of Document*
