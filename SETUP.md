# 🏥 Medical AI Chatbot - Setup Guide

This guide will help you set up and run the Medical AI Chatbot on your local machine.

## 📋 Prerequisites

- **Python 3.10+** (Make sure it's added to your system PATH)
- **Git** (Optional, for cloning)
- **API Keys**:
    - **Groq API Key** (Required for the LLM) - [Get one here](https://console.groq.com/)
    - **Tavily API Key** (Required for web search) - [Get one here](https://tavily.com/)
    - **HuggingFace Token** (Required for embeddings) - [Get one here](https://huggingface.co/settings/tokens)

## 🚀 Quick Start (Windows)

We have included a startup script to automate the process.

1.  **Clone/Download** the repository.
2.  **Create a `.env` file** in the `medical_agent` directory (see Configuration below).
3.  Double-click **`run_app.bat`**.

This script will automatically:
- Create a virtual environment (`.venv`)
- Install all dependencies
- Start the server at `http://localhost:8000`

---

## 🛠️ Manual Installation

If you prefer to set it up manually or are on Mac/Linux:

### 1. Create `.env` Configuration
Duplicate `.env.example` (if available) or create a new `.env` file in the root directory:

```env
GROQ_API_KEY=gsk_...
TAVILY_API_KEY=tvly-...
HUGGINGFACE_API_KEY=hf_...
PUBMED_API_KEY=... (Optional)
```

### 2. Set up Virtual Environment

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**Mac/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Build Knowledge Base (Optional)
If you want to rebuild the disease database for the RAG agent:
```bash
python src/tools/rag/retriever.py
```

### 5. Run the Application
```bash
python web/app.py
```

Visit **`http://localhost:8000`** in your browser.

## 📦 Project Structure

- **`src/`**: Backend source code
    - **`langgraph/`**: Core logic and nodes (Decider, Aggregator, Safety)
    - **`tools/`**: Individual tools (RAG, Research, Web Search)
- **`web/`**: Frontend files
    - **`static/`**: HTML, CSS, and JS assets
- **`data/`**: Datasets and FAISS index
- **`run_app.bat`**: Windows startup script

## 👷 Troubleshooting

- **"Module not found" error**: Ensure your virtual environment is activated (`.venv`).
- **Web search failing**: Check your `TAVILY_API_KEY` in `.env`.
- **LLM errors**: Check your `GROQ_API_KEY` and ensure you haven't hit rate limits.
