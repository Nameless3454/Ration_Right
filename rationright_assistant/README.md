# RationRight AI Assistant (Version 1)

A standalone AI operations assistant for India's Public Distribution System (PDS) platform, **RationRight**. It answers operational, inventory, beneficiary, and audit queries strictly using weekly imported datasets and official data dictionary documentation.

---

## 1. Architecture Principles

The assistant adopts a hybrid architecture to ensure 100% data fidelity, zero hallucination, and high explainability:

- **Structured Queries (SQLite)**: Executes deterministic, read-only parameterized queries for calculations, aggregations, counts, shop performance rankings, and weekly snapshot comparisons.
- **RAG Knowledge Base (ChromaDB + Sentence Transformers)**: Semantic retrieval for schema definitions, NFSA welfare category quotas (AAY vs. PHH), system flags (`possible_duplicate`, `multiple_claims`), and field documentation.
- **Intent Router**: Automatically analyzes natural language questions and routes them to safe SQL execution, semantic vector search, a hybrid combination, or rejects out-of-domain queries.
- **Grounded Response Generation (Google Gemini API)**: Synthesizes structured administrative answers strictly based on verified database queries and retrieved documentation chunks, enforcing mandatory batch citations, administrative neutrality, and strict refusal of external knowledge.
- **Security & Read-Only Boundaries**: No unrestricted arbitrary SQL generation by LLM. Never declares any beneficiary "fraudulent" or makes final administrative decisions.

---

## 2. Dependencies & Prerequisites

- **Operating System**: macOS / Linux
- **Python Version**: Python 3.10+ (Tested on Python 3.11)
- **Key Python Packages**:
  - `fastapi` & `uvicorn`: Web framework and ASGI server
  - `pydantic` & `pydantic-settings`: Data validation and settings management
  - `sqlite3`: Relational storage for weekly snapshots (standard library)
  - `chromadb`: Local vector database for semantic retrieval
  - `sentence-transformers`: Local embedding generation (`all-MiniLM-L6-v2`)
  - `google-genai`: Official Google Gemini API client
  - `pytest` & `httpx`: Testing suite and test HTTP client

---

## 3. Environment Setup & Installation

### Step 1: Navigate to the Assistant Directory
```bash
cd rationright_assistant
```

### Step 2: Create and Activate Virtual Environment
```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Environment Variables
Create a `.env` file in `rationright_assistant/`:
```env
ENVIRONMENT=development
PORT=8000
HOST=0.0.0.0
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
```
*(Note: If `GEMINI_API_KEY` is omitted, the assistant uses a deterministic, audit-compliant grounded generator that formats the verified SQL and RAG evidence with identical citation and neutrality guarantees.)*

---

## 4. Running the API

Start the standalone development server with Uvicorn:
```bash
PYTHONPATH=rationright_assistant uvicorn src.api.main:app --reload --port 8000
```
The server will start at `http://localhost:8000`. Interactive OpenAPI documentation is available at `http://localhost:8000/docs`.

---

## 5. API Endpoints & Usage

### Primary AI Assistant Endpoint (`POST /api/chat`)
Answers questions strictly using imported weekly datasets and system documentation:
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Which records have duplicate flags?"
  }'
```
**Response (200 OK):**
```json
{
  "answer": "**Dataset Citation:** `RationRight_Dummy_Pack_Week_42` (Import ID: `IMP_20261102_165712_534397`)\n\n### Records with Duplicate Flags (2 found):\n\n- **Beneficiary ID `BEN007`** (Ration Card: `DEMO-RC-10007`, Shop: `Jan Seva Ration Kendra`):\n  *Reason:* Same demo household fingerprint as BEN014\n- **Beneficiary ID `BEN014`** (Ration Card: `DEMO-RC-10014`, Shop: `Bharat Ration Point`):\n  *Reason:* Same demo household fingerprint as BEN007\n\n> [!NOTE]\n> Every flag is strictly an administrative review lead to guide human field inspection. It is not evidence of fraud, and cardholders retain the statutory right to verification and appeal.",
  "route_type": "STRUCTURED",
  "intent": "DUPLICATE_FLAGS_QUERY",
  "import_id_cited": "IMP_20261102_165712_534397",
  "dataset_name_cited": "RationRight_Dummy_Pack_Week_42",
  "is_supported": true
}
```

### Multipart Dataset Upload (`POST /api/import/upload`)
Upload weekly dataset archives (ZIP, single CSV, or JSON) with zip-slip traversal protection and 50MB payload limits:
```bash
curl -X POST http://localhost:8000/api/import/upload \
  -F "file=@weekly_dataset.zip" \
  -F "dataset_name=Week_43_Snapshot"
```

### Paginated Inventory & Metrics Endpoints
Retrieve paginated inventory ledgers and snapshot metrics:
```bash
# Metrics with paginated inventory
curl -X GET "http://localhost:8000/api/metrics/latest?limit=10&offset=0"

# Dedicated paginated inventory endpoint
curl -X GET "http://localhost:8000/api/inventory/latest?commodity=Rice&limit=10&offset=0"
```

### Strict Domain Routing & Accusation Defense
- **Strict Domain Routing**: Questions require positive evidence of relating to the RationRight/PDS domain (`beneficiary`, `card`, `shop`, `inventory`, `stock`, `audit`, `transaction`, `quota`, `rice`, `wheat`, `summary`, `status`). Contextual follow-up queries (e.g., "Why?", "Show details", "Tell me more") are supported. Out-of-domain questions ("Write a Python script", "How to bake bread") are strictly routed to `RouteType.UNSUPPORTED` without LLM fallback.
- **Accusation Neutrality**: Identifiers (`BEN\d+`, `PWD\d+`, `DLR\d+`) and accusatory prompts ("fraud", "corrupt", "scam", "criminal", "guilty") automatically trigger administrative neutrality disclaimers, distinguishing review leads from confirmed wrongdoing.

### Out-of-Domain Refusal Example:
```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the capital of France?"
  }'
```
**Response:**
```json
{
  "answer": "The imported RationRight datasets do not contain information to answer this question. The assistant answers questions strictly using weekly imported RationRight datasets and official system documentation.",
  "route_type": "UNSUPPORTED",
  "intent": "OUT_OF_DOMAIN",
  "is_supported": false
}
```

---

## 6. Running Tests

Run the full Pytest suite (66/66 tests passing):
```bash
PYTHONPATH=rationright_assistant ./rationright_assistant/.venv/bin/pytest ./rationright_assistant/tests -v
```

---

## 7. Conversational Response Presentation

The assistant formats all chat responses as natural, professional executive briefings:
1. **Direct Answer First**: Conversational answer presented immediately without raw database dumps.
2. **Key Operational Findings**: Concise bulleted highlights and structured Markdown comparison tables.
3. **Administrative Neutrality**: Enforces official neutrality disclaimers whenever flagged records, review reasons, or allegations are queried.
4. **Secondary Source Attribution**: Cites the exact weekly import dataset name and `import_id` at the bottom of the response.
5. **Verified Evidence Accordion**: Officials can optionally expand the evidence accordion in the UI to inspect raw SQLite outputs and ChromaDB vector snippets.

---

## 8. Running the Standalone Frontend

The standalone React + Vite + Tailwind CSS operations frontend is located in `rationright_assistant/frontend/`.

### Prerequisites & Dependencies
- Node.js 18+ (tested on Node v26)
- Dependencies installed in `rationright_assistant/frontend/node_modules`

### Development Server
To run the standalone frontend development server:
```bash
cd rationright_assistant/frontend
npm run dev
```
The standalone frontend starts on `http://localhost:5174` and connects to `http://localhost:8001` via `VITE_API_BASE_URL`.

---

## 9. Running the Integrated RationRight Application

The assistant is integrated as a floating chatbot accessible across all 11 routes of the main RationRight application (`frontend/`).

### Step 1: Start Assistant FastAPI Backend (Port 8001)
```bash
cd rationright_assistant
source .venv/bin/activate
uvicorn src.api.main:app --host 127.0.0.1 --port 8001 --reload
```

### Step 2: Start Integrated Frontend (Port 5173)
```bash
cd frontend
npm run dev
```
Open your browser at `http://localhost:5173/static/` to interact with the full RationRight platform (Overview, Beneficiaries, Distribution, Inventory, Reports, Alerts) with the **RationRight AI Assistant** floating in the bottom-right corner.

### Production Build
To create an optimized production build:
```bash
cd rationright_assistant/frontend
npm run build
```
Built artifacts are compiled into `rationright_assistant/frontend/dist/`.

---

## 8. Running Both Backend & Frontend Concurrently

### Terminal 1: FastAPI Backend
```bash
cd rationright_assistant
source .venv/bin/activate
uvicorn src.api.main:app --reload --port 8001
```

### Terminal 2: Vite Frontend
```bash
cd rationright_assistant/frontend
npm run dev
```
Open your browser at `http://localhost:5174` to interact with the Operations Dashboard, inspect weekly snapshots, upload datasets, and query the Floating AI Assistant.
