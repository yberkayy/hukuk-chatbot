# Hukuk AI SaaS

Hukuk AI is a comprehensive legal assistant SaaS application designed to answer questions about Turkish Law using a Retrieval-Augmented Generation (RAG) architecture. It features a robust Python FastAPI backend for AI model integration and a sleek, modern Next.js 14 frontend.

---

## 🏗️ Architecture Overview

The system is separated into two main components:
1. **Backend** (`/backend`): A FastAPI Python server handling document ingestion, Chroma vector database storage, and OpenAI LLM streaming.
2. **Frontend** (`/frontend`): A Next.js 14 (App Router) React application serving as the UI, utilizing Tailwind CSS and Server-Sent Events (SSE) for real-time streaming.

---

## ⚙️ Backend Setup & Configuration

The backend requires Python 3.10+ and uses an OpenAI model to process legal questions.

### 1. Installation
Navigate to the backend directory and install dependencies:
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```
  
### 2. Environment Variables (.env)
Create a `.env` file in the `backend/` directory. Use the `.env.example` file as a reference:
```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o
ADMIN_API_KEY=your_secure_admin_key_here
SIMILARITY_THRESHOLD=0.75
```
*Note: `ADMIN_API_KEY` is required to securely upload new documents to the RAG database.*

### 3. Running the Server
Run the FastAPI application via `uvicorn`:
```bash
python -m uvicorn app.main:app --reload --port 8000
```
The API will be accessible at `http://localhost:8000`.

---

## 📂 Document Management (Admin)

The backend features an admin endpoint to securely upload and embed PDF files directly into the persistent Chroma Vector DB.

**Endpoint:** `POST /admin/upload`
**Features:**
- Duplicates prevention (skips existing identical chunks).
- Automatic text splitting and `intfloat/multilingual-e5-large` HuggingFace Embeddings.
- Persists data to the `/backend/chroma_db` and `/backend/data` directories.

**Usage Example via cURL:**
```bash
curl -X POST "http://localhost:8000/admin/upload" \
  -H "X-API-Key: your_secure_admin_key_here" \
  -F "file=@/path/to/kanun_maddesi.pdf"
```

---

## 💻 Frontend Setup & Configuration

The frontend provides the Chat Interface for the application.

### 1. Installation
Navigate to the frontend directory:
```bash
cd frontend
npm install
```

### 2. API Proxy
The Next.js configuration (`next.config.mjs`) automatically routes `/api/` fetch requests to `http://localhost:8000/`. No `.env` is required for the frontend local bridging.

### 3. Running the App
Start the development server:
```bash
npm run dev
```
Open `http://localhost:3000` in your web browser.

---

## ✅ Deployment Checklist

Before moving to production, ensure:
1. **API Keys are Secured**: Do not bake keys into Docker images. Use secrets managers or CI environment variables.
2. **Persistent Storage**: Ensure `/backend/chroma_db` and `/backend/data` are mounted as persistent volumes in Docker.
3. **SSE Proxy Settings**: If deploying behind NGINX, disable buffering to retain the streaming chunks:
   ```nginx
   proxy_buffering off;
   proxy_set_header Validation-Connection "keep-alive";
   ```
4. **Build Frontend**: Run `npm run build` in the frontend directory to produce the static and server-rendered HTML.
