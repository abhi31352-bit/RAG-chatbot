# Product Requirements Document (PRD)
## RAG Chatbot for Class Demo

---

| Field | Details |
|-------|---------|
| **Product Name** | Class RAG Chatbot |
| **Document Version** | 1.0 |
| **Date** | 2026-09-27 |
| **Status** | Draft |
| **Author** | — |

---

## 1. Problem Statement

Instructors and students in classroom settings often struggle with:
- **Information overload**: Course materials (lecture slides, textbooks, notes, assignments) are scattered across multiple formats and locations.
- **Repetitive Q&A**: Instructors answer the same questions repeatedly during and after class.
- **Limited accessibility**: Students may not have immediate access to course content outside of class hours.
- **Lack of engagement**: Static documents do not adapt to individual student learning paces or curiosity.

There is a need for an intelligent, interactive chatbot that can **retrieve relevant information from course-specific documents** and **generate accurate, contextually appropriate responses** — all within a simple interface suitable for a live class demonstration.

---

## 2. Goals & Objectives

### Primary Goal
Build a **Retrieval-Augmented Generation (RAG) chatbot** that answers questions based on course-specific documents, demonstrating the power of combining information retrieval with large language models.

### Objectives
1. **Accurate Retrieval**: Retrieve the most relevant passages from uploaded course documents.
2. **Contextual Generation**: Generate coherent, accurate answers grounded in retrieved content.
3. **Real-time Interaction**: Provide responses within a few seconds for live demo purposes.
4. **Simple Interface**: Offer a clean, intuitive chat UI that works well in a classroom projection setting.
5. **Easy Document Management**: Allow instructors to upload, update, and manage course documents with minimal effort.

---

## 3. Target Users

| User | Description | Primary Use Case |
|------|-------------|------------------|
| **Instructors** | Professors, TAs, or guest lecturers demonstrating RAG technology | Upload course materials, demo the chatbot, showcase AI capabilities |
| **Students** | Class attendees interacting with the chatbot during/after demo | Ask questions about course content, explore how RAG works |
| **Evaluators** | Judges, peers, or stakeholders assessing the project | Evaluate technical implementation, usability, and demo effectiveness |

---

## 4. Scope

### In Scope
- Upload and processing of course documents (PDF, TXT, DOCX, Markdown)
- Document chunking and embedding into a vector store
- Semantic search / similarity retrieval
- LLM-based answer generation with retrieved context
- Web-based chat interface (single-page application)
- Basic conversation history within a session
- Source citation display (show which document/section the answer came from)
- Simple admin panel for document management

### Out of Scope
- User authentication and multi-tenant support
- Multi-language support (English only for demo)
- Mobile-native apps (web responsive is sufficient)
- Advanced features like file annotation, highlighting, or collaborative editing
- Integration with LMS platforms (Canvas, Blackboard, etc.)
- Production-grade deployment (scalability, monitoring, CI/CD)

---

## 5. Features & Requirements

### 5.1 Document Upload & Processing
| ID | Feature | Priority | Description |
|----|---------|----------|-------------|
| F-01 | Document Upload | P0 | Instructors can upload files (PDF, TXT, DOCX, MD) via drag-and-drop or file picker |
| F-02 | Document Parsing | P0 | System extracts text content from uploaded files |
| F-03 | Document Chunking | P0 | Extracted text is split into manageable chunks (e.g., 500–1000 tokens with overlap) |
| F-04 | Embedding Generation | P0 | Each chunk is converted into vector embeddings using an embedding model |
| F-05 | Vector Storage | P0 | Embeddings are stored in a vector database for similarity search |
| F-06 | Document Management | P1 | Instructors can view, delete, or re-upload documents |

### 5.2 Retrieval System
| ID | Feature | Priority | Description |
|----|---------|----------|-------------|
| F-07 | Query Embedding | P0 | User questions are converted into embeddings |
| F-08 | Similarity Search | P0 | System retrieves top-K most relevant chunks from the vector store |
| F-09 | Context Assembly | P0 | Retrieved chunks are assembled into a context prompt for the LLM |
| F-10 | Source Tracking | P1 | Each retrieved chunk retains metadata about its source document |

### 5.3 Answer Generation
| ID | Feature | Priority | Description |
|----|---------|----------|-------------|
| F-11 | LLM Integration | P0 | System sends context + question to an LLM (e.g., GPT-4, Claude, or open-source alternative) |
| F-12 | Grounded Responses | P0 | LLM generates answers strictly based on retrieved context |
| F-13 | Fallback Handling | P1 | If no relevant context is found, the chatbot responds with a graceful "I don't know" message |
| F-14 | Source Citation | P1 | Responses include references to the source documents/chunks used |

### 5.4 Chat Interface
| ID | Feature | Priority | Description |
|----|---------|----------|-------------|
| F-15 | Chat UI | P0 | Clean, responsive web interface with message bubbles |
| F-16 | Message History | P0 | Conversation history maintained during the session |
| F-17 | Typing Indicator | P1 | Visual feedback while the system is processing |
| F-18 | Suggested Questions | P2 | Pre-populated example questions to guide users |
| F-19 | Clear Conversation | P1 | Button to reset the conversation history |

### 5.5 Admin Panel
| ID | Feature | Priority | Description |
|----|---------|----------|-------------|
| F-20 | Document List | P1 | View all uploaded documents with status |
| F-21 | Delete Documents | P1 | Remove documents and their embeddings from the system |
| F-22 | System Status | P2 | Basic health check (vector store connection, LLM availability) |

---

## 6. Technical Architecture

### 6.1 High-Level Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Web UI    │────▶│  API Server      │────▶│  Vector Store   │
│  (React)    │◀────│  (Python/FastAPI)│◀────│  (Chroma/Pinecone│
└─────────────┘     └────────┬─────────┘     │  /Weaviate)      │
                             │               └─────────────────┘
                             │
                    ┌────────▼─────────┐
                    │   LLM Service    │
                    │ (OpenAI/Claude/  │
                    │  Local Model)    │
                    └──────────────────┘
```

### 6.2 Technology Stack (Suggested)

| Layer | Technology Options |
|-------|-------------------|
| **Frontend** | React, Next.js, or plain HTML/JS |
| **Backend** | Python (FastAPI or Flask) |
| **Embedding Model** | OpenAI `text-embedding-3-small`, `sentence-transformers/all-MiniLM-L6-v2` |
| **Vector Database** | Chroma (local, easy demo), Pinecone, or Weaviate |
| **LLM** | `big-pickle` (`LLM_MODEL`), called through the OpenAI SDK. Must degrade to a clearly-labelled offline extractive mode when no usable API key is configured, so the demo is never dead. |
| **Document Parsing** | pypdf, python-docx (LangChain is unusable here: `langchain-chroma` is not on PyPI and `langchain-community` requires Python ≥ 3.10) |
| **Orchestration** | Hand-rolled RAG pipeline — the flow is short enough that a framework adds more dependency risk than it removes |
| **Deployment** | Local machine or cloud (Vercel + Railway/Render) |

### 6.3 RAG Pipeline Flow

1. **Document Ingestion**: Upload → Parse → Chunk → Embed → Store
2. **Query Processing**: User question → Embed → Similarity search → Retrieve top-K chunks
3. **Prompt Construction**: System prompt + Retrieved context + User question
4. **Answer Generation**: LLM generates grounded response
5. **Response Delivery**: Answer + Source citations returned to UI

---

## 7. User Stories

| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| US-01 | As an instructor, I want to upload my lecture slides so that the chatbot can answer questions about them | Files upload successfully, are parsed, and appear in the document list |
| US-02 | As a student, I want to ask a question and get an answer based on the course materials | Response is accurate, relevant, and cites the source document |
| US-03 | As an instructor, I want to delete outdated documents so that the chatbot doesn't use them | Document and its embeddings are removed; subsequent queries don't reference it |
| US-04 | As a student, I want to see which document the answer came from | Each response includes a clickable source reference |
| US-05 | As an instructor, I want to reset the conversation so that the demo starts fresh | Chat history is cleared; new questions don't reference previous context |
| US-06 | As a student, I want the chatbot to tell me when it doesn't know the answer | Graceful fallback message instead of hallucinated answers |

---

## 8. Non-Functional Requirements

| Category | Requirement |
|----------|-------------|
| **Performance** | Response time < 5 seconds for typical queries |
| **Scalability** | Support up to 50 concurrent users (classroom size) |
| **Availability** | 99% uptime during demo period |
| **Security** | No sensitive data stored; documents are ephemeral or access-controlled |
| **Usability** | UI readable from projector; minimal clicks to start chatting |
| **Maintainability** | Clean, documented code; easy to swap components (LLM, vector DB) |

---

## 9. Success Metrics

| Metric | Target |
|--------|--------|
| Answer accuracy (relevance to question) | > 85% |
| Response time (p95) | < 5 seconds |
| Document processing success rate | > 95% |
| User satisfaction (post-demo survey) | > 4.0 / 5.0 |
| Hallucination rate (answers not grounded in context) | < 5% |

---

## 10. Constraints & Assumptions

### Constraints
- **Demo-focused**: System is optimized for a live class demonstration, not production use.
- **English only**: All documents and interactions are in English.
- **Limited document size**: Total document size should not exceed ~50 MB for smooth processing.
- **API costs**: LLM API usage should be monitored to avoid unexpected costs during demo.

### Assumptions
- Course documents are in digital format (PDF, TXT, DOCX, or Markdown).
- The classroom has reliable internet access (if using cloud-based LLM/embeddings).
- Instructors have basic technical literacy to upload documents and manage the system.
- The demo audience is familiar with chatbot interfaces.

---

## 11. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| LLM hallucination (answers not grounded in docs) | High | Strict prompting, fallback handling, source citation |
| Slow response times during demo | Medium | Pre-warm connections, use fast embedding models, cache frequent queries |
| Document parsing failures (scanned PDFs, images) | Medium | Support OCR for scanned documents; validate uploads |
| API rate limits or outages | Medium | Have a backup LLM provider; queue requests gracefully |
| Vector store corruption or data loss | Low | Regular backups; re-indexing capability |

---

## 12. Timeline & Milestones

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| **Phase 1: Core RAG Pipeline** | Week 1–2 | Document upload, parsing, chunking, embedding, vector storage |
| **Phase 2: Chat Interface** | Week 2–3 | Web UI, message history, typing indicator |
| **Phase 3: Answer Generation** | Week 3–4 | LLM integration, grounded responses, source citations |
| **Phase 4: Admin & Polish** | Week 4–5 | Document management, suggested questions, UI polish |
| **Phase 5: Testing & Demo Prep** | Week 5–6 | End-to-end testing, performance optimization, demo rehearsal |

---

## 13. Open Questions

1. Should the system support multiple courses/subjects, or is it single-course for the demo?
2. Should we use a cloud-based LLM (OpenAI/Claude) or a local open-source model for the demo?
3. Do we need conversation persistence across sessions, or is in-memory session history sufficient?
4. Should the chatbot support follow-up questions with conversation context (multi-turn)?
5. What is the preferred deployment target — local machine, cloud, or both?

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **RAG** | Retrieval-Augmented Generation — combining information retrieval with LLM generation |
| **Embedding** | Numerical vector representation of text that captures semantic meaning |
| **Vector Store** | Database optimized for storing and searching vector embeddings |
| **Chunking** | Splitting large documents into smaller, manageable pieces for retrieval |
| **Hallucination** | When an LLM generates plausible but incorrect or fabricated information |
| **Grounding** | Ensuring LLM responses are based on retrieved, factual context |

---

*End of Document*
