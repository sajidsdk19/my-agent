<div align="center">

# 🦞 Claw Agent

**An AI coding agent that never exhausts — runs locally for free, or on Gemini cloud.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![Ollama](https://img.shields.io/badge/Backend-Ollama%20%7C%20Gemini-purple)](https://ollama.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

**Author:** [Sajid Khan](https://sajidkhan.me) · CTO, TechScape  
**GitHub:** [github.com/sajidsdk19](https://github.com/sajidsdk19)

</div>

---

## Overview

Claw Agent is a self-hosted AI coding assistant built on the **Claw Code architecture**. It supports two LLM backends:

| Backend | Cost | Requires |
|---|---|---|
| **Ollama** (local) | 🟢 Free forever, no limits | Ollama installed + any model pulled |
| **Gemini 2.5 Flash** (cloud) | ☁️ 1500 req/day free tier | `GEMINI_API_KEY` env var |

It ships with **three interfaces** — a Desktop GUI, a Web UI, and a Terminal REPL — all powered by the same `agent.py` core.

---

## Project Structure

```
my-agent/
├── agent.py          # Core — LLM backends, tools, agent loop
├── desktop_app.py    # Desktop GUI (CustomTkinter)
├── app.py            # Web UI server (Flask + SSE streaming)
├── requirements.txt  # Python dependencies
├── templates/
│   └── index.html    # Web UI frontend
└── style.css         # Web UI styles
```

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | Must be on your PATH |
| pip | latest | For installing dependencies |
| [Ollama](https://ollama.com) | any | Only needed for local/free backend |
| Gemini API Key | — | Only needed for cloud backend |

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/sajidsdk19/my-agent.git
cd my-agent
```

### 2. Install Python dependencies

```bash
pip install -r requirements.txt
```

This installs:

| Package | Purpose |
|---|---|
| `ollama` | Python client for the local Ollama backend |
| `google-genai` | Google Gemini API client |
| `rich` | Beautiful terminal output (colors, markdown) |
| `duckduckgo-search` | Web search tool for the agent |
| `requests` | HTTP utilities |
| `flask` | Web UI server |
| `customtkinter` | Desktop GUI framework |

### 3. (Optional) Install Ollama for local/free usage

Download from [ollama.com](https://ollama.com), then pull a model:

```bash
ollama pull qwen2.5-coder     # recommended coding model
# or
ollama pull llama3.2
```

### 4. (Optional) Set Gemini API key for cloud usage

Get a free key at [aistudio.google.com](https://aistudio.google.com), then:

```bash
# Windows
set GEMINI_API_KEY=your_key_here

# macOS/Linux
export GEMINI_API_KEY=your_key_here
```

---

## Running the Agent

### 🖥️ Desktop App (recommended)

A fully-featured GUI with file explorer, tabbed code editor, syntax highlighting, and live chat.

```bash
python desktop_app.py
```

**Features:**
- Sidebar with model selector + live Ollama refresh
- 4-pane layout: Explorer · Chat · Code Editor
- File tree with expand/collapse, right-click context menu
- Syntax highlighting for Python, JS/TS, C/C++/C#, Go, Rust, Java, HTML, CSS, JSON, Bash, Markdown
- AI Review and AI Revamp buttons per open file
- Session save and clear controls
- Status panel showing model, turns, and idle/busy state

---

### 🌐 Web UI

A browser-based chat interface with real-time streaming via Server-Sent Events (SSE).

```bash
python app.py
```

Then open → **http://localhost:5000**

**Features:**
- Model picker (Ollama or Gemini)
- Streaming responses — tokens appear as they're generated
- Session persistence per browser tab
- REST API endpoints (see below)

#### API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves the Web UI |
| `GET` | `/api/models` | Lists available models |
| `POST` | `/api/chat` | Starts a new agent turn, returns `stream_id` |
| `GET` | `/api/stream/<id>` | SSE stream for a running turn |
| `POST` | `/api/session/clear` | Clears conversation history |
| `POST` | `/api/session/save` | Saves session to disk |
| `GET` | `/api/status` | Returns current model, turns, CWD |

---

### 💻 Terminal REPL

A rich interactive terminal experience, great for quick tasks.

```bash
# Auto-detect backend (prefers Ollama, falls back to Gemini)
python agent.py

# One-shot prompt
python agent.py "explain this codebase"

# Force a specific backend
python agent.py --model gemini
python agent.py --model qwen2.5-coder

# List all available Ollama models
python agent.py --list-models
```

---

## How It Works

### Agent Loop

```
User prompt
    │
    ▼
LLM Backend (Ollama or Gemini)
    │
    ├── Returns text? ──► Display to user, wait for next input
    │
    └── Returns tool_calls?
            │
            ▼
        Execute tool(s)  ──► bash / read_file / write_file / grep_search / ...
            │
            ▼
        Append tool result to message history
            │
            ▼
        Send back to LLM (loop until no more tool calls)
```

The agent runs in a **multi-turn tool loop** — it keeps calling tools and feeding results back to the LLM until the model produces a final text response.

### Session Persistence

Sessions are saved as JSON files at:

```
~/.claw-agent/sessions/<timestamp>.json
```

Each session contains the full message history including tool calls and results.

---

## Agent Tools

The agent has access to 8 built-in tools:

| Tool | Icon | Description |
|---|---|---|
| `bash` | 💻 | Execute shell commands (git, pip, compile, test, etc.) |
| `read_file` | 📖 | Read file contents (with optional line range) |
| `write_file` | 📝 | Create or overwrite a file |
| `edit_file` | ✏️ | Targeted string replacement in a file |
| `list_dir` | 📁 | List directory contents |
| `glob_search` | 🔎 | Find files by pattern (e.g. `**/*.py`) |
| `grep_search` | 🔍 | Regex search across source files |
| `web_search` | 🌐 | DuckDuckGo web search |

---

## Backend Details

### Ollama (Local)

- Connects to `http://localhost:11434`
- Supports any model installed via `ollama pull`
- Fully streaming — tokens appear in real-time
- No API key, no rate limits, no internet required
- Tool calls are returned in bulk at end of stream (Ollama limitation)

### Gemini 2.5 Flash (Cloud)

- Uses the `google-genai` SDK
- Free tier: **1500 requests/day** via [Google AI Studio](https://aistudio.google.com)
- Paid: ~$0.30 / 1M input tokens
- Requires `GEMINI_API_KEY` environment variable
- Note: streaming for tool-call turns is not yet supported (text-only turns stream)

---

## Configuration

All configuration is done via environment variables or command-line flags — no config files needed.

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(none)* | Required for Gemini backend |
| `GOOGLE_API_KEY` | *(none)* | Alternative to `GEMINI_API_KEY` |
| `FLASK_SECRET` | random | Flask session secret (set for production) |

---

## Troubleshooting

### Ollama models not showing
Make sure Ollama is running: `ollama serve` then refresh models in the desktop app or restart the server.

### `GEMINI_API_KEY not set` error
Set the environment variable before running: `set GEMINI_API_KEY=your_key`

### Desktop app fonts look wrong
Install the fonts used by the app: **Inter** and **JetBrains Mono** from Google Fonts. The app will fall back to system fonts if unavailable.

### Web UI not streaming
Ensure no proxy or firewall is blocking SSE on `localhost:5000`. Try opening directly in the browser without a proxy.

---

## License

MIT License — free to use, modify, and distribute.

---

<div align="center">

Built with ❤️ by **[Sajid Khan](https://sajidkhan.me)** · CTO, TechScape  
[sajidkhan.me](https://sajidkhan.me) · [github.com/sajidsdk19](https://github.com/sajidsdk19)

</div>
