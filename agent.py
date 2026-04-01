#!/usr/bin/env python3
import sys, io
# Force UTF-8 output on Windows so emoji don't crash the terminal
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

"""
+------------------------------------------------------------------+
║   🦞  CLAW AGENT  —  AI Coding Agent That Never Exhausts        ║
║   Built on Claw Code architecture                                ║
║                                                                  ║
║   Backends:                                                      ║
║     • Ollama  (local, 100% FREE — NO limits, forever)           ║
║     • Gemini  2.5 Flash (free tier: 500 req/day)                ║
╚══════════════════════════════════════════════════════════════════╝

Usage:
  python agent.py                        # Interactive REPL (auto-detects backend)
  python agent.py "fix the bug"         # One-shot prompt
  python agent.py --model gemini        # Force Gemini
  python agent.py --model qwen2.5-coder # Force specific Ollama model
  python agent.py --list-models         # Show available models
"""

import os
import json
import subprocess
import glob as glob_module
import re
import shutil
import datetime
import argparse
import textwrap
from pathlib import Path
from typing import Any, Optional

# ─── Rich UI (pretty terminal) ───────────────────────────────────────────────
try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.text import Text
    from rich.syntax import Syntax
    from rich.table import Table
    from rich.live import Live
    from rich.spinner import Spinner
    from rich.rule import Rule
    from rich.prompt import Prompt
    RICH = True
    console = Console()
except ImportError:
    RICH = False
    console = None

# ─── Backend availability checks ─────────────────────────────────────────────
OLLAMA_OK = False
GEMINI_OK = False
DDG_OK = False

try:
    import ollama as _ollama_lib
    OLLAMA_OK = True
except ImportError:
    pass

try:
    from google import genai as genai_new
    GEMINI_OK = True
except ImportError:
    pass

try:
    from duckduckgo_search import DDGS
    DDG_OK = True
except ImportError:
    pass

# ─── Globals ─────────────────────────────────────────────────────────────────
SESSION_DIR = Path.home() / ".claw-agent" / "sessions"
SESSION_DIR.mkdir(parents=True, exist_ok=True)

CWD = Path.cwd()


# ══════════════════════════════════════════════════════════════════════════════
#  TOOLS — What the agent can DO
# ══════════════════════════════════════════════════════════════════════════════

TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": (
                "Execute a bash/shell command on the local machine. "
                "Use for running code, installing packages, git operations, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute.",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default 30).",
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file from the filesystem.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Absolute or relative path to the file.",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "First line to read (1-indexed, optional).",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Last line to read (1-indexed, optional).",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write (or overwrite) a file with new content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to create or overwrite.",
                    },
                    "content": {
                        "type": "string",
                        "description": "Full content to write to the file.",
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": (
                "Replace a specific string in a file with new content. "
                "More targeted than write_file — only changes what you specify."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file."},
                    "old_string": {
                        "type": "string",
                        "description": "Exact text to find and replace.",
                    },
                    "new_string": {
                        "type": "string",
                        "description": "Text to insert in place of old_string.",
                    },
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List the contents of a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path (defaults to current dir).",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "glob_search",
            "description": "Find files matching a glob pattern (e.g. '**/*.py').",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Glob pattern like '**/*.ts' or 'src/*.py'.",
                    },
                    "directory": {
                        "type": "string",
                        "description": "Root directory to search from (optional).",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "grep_search",
            "description": "Search for a regex pattern across files. Returns matching lines with filenames.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Regex pattern to search for.",
                    },
                    "path": {
                        "type": "string",
                        "description": "File or directory to search in.",
                    },
                    "case_insensitive": {
                        "type": "boolean",
                        "description": "Case-insensitive search (default false).",
                    },
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web using DuckDuckGo. Returns titles and snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query string.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Number of results to return (default 5).",
                    },
                },
                "required": ["query"],
            },
        },
    },
]


def _resolve_path(path: str) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = CWD / p
    return p


def tool_bash(command: str, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(CWD),
        )
        out = result.stdout
        err = result.stderr
        code = result.returncode
        parts = []
        if out.strip():
            parts.append(out.rstrip())
        if err.strip():
            parts.append(f"[stderr]\n{err.rstrip()}")
        if code != 0:
            parts.append(f"[exit code: {code}]")
        return "\n".join(parts) if parts else "(no output)"
    except subprocess.TimeoutExpired:
        return f"[error] Command timed out after {timeout}s"
    except Exception as exc:
        return f"[error] {exc}"


def tool_read_file(path: str, start_line: int = None, end_line: int = None) -> str:
    try:
        p = _resolve_path(path)
        text = p.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines(keepends=True)
        if start_line or end_line:
            s = (start_line or 1) - 1
            e = end_line or len(lines)
            lines = lines[s:e]
        content = "".join(lines)
        if len(content) > 50_000:
            content = content[:50_000] + "\n... [truncated at 50 000 chars]"
        return content
    except FileNotFoundError:
        return f"[error] File not found: {path}"
    except Exception as exc:
        return f"[error] {exc}"


def tool_write_file(path: str, content: str) -> str:
    try:
        p = _resolve_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"✅ Written {len(content)} chars to {p}"
    except Exception as exc:
        return f"[error] {exc}"


def tool_edit_file(path: str, old_string: str, new_string: str) -> str:
    try:
        p = _resolve_path(path)
        original = p.read_text(encoding="utf-8")
        if old_string not in original:
            return f"[error] String not found in {path}:\n{old_string[:200]}"
        count = original.count(old_string)
        updated = original.replace(old_string, new_string, 1)
        p.write_text(updated, encoding="utf-8")
        return f"✅ Replaced 1/{count} occurrence(s) in {p}"
    except FileNotFoundError:
        return f"[error] File not found: {path}"
    except Exception as exc:
        return f"[error] {exc}"


def tool_list_dir(path: str = ".") -> str:
    try:
        p = _resolve_path(path)
        entries = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
        lines = []
        for e in entries:
            if e.is_dir():
                lines.append(f"📁  {e.name}/")
            else:
                size = e.stat().st_size
                size_str = f"{size:>8,} B"
                lines.append(f"📄  {e.name:<40} {size_str}")
        return f"{p}\n" + "\n".join(lines) if lines else f"{p}\n(empty)"
    except Exception as exc:
        return f"[error] {exc}"


def tool_glob_search(pattern: str, directory: str = None) -> str:
    try:
        root = _resolve_path(directory) if directory else CWD
        matches = list(root.glob(pattern))
        if not matches:
            return "(no matches)"
        lines = [str(m.relative_to(root)) for m in matches[:100]]
        result = "\n".join(lines)
        if len(matches) > 100:
            result += f"\n... and {len(matches)-100} more"
        return result
    except Exception as exc:
        return f"[error] {exc}"


def tool_grep_search(pattern: str, path: str = ".", case_insensitive: bool = False) -> str:
    try:
        flags = re.IGNORECASE if case_insensitive else 0
        compiled = re.compile(pattern, flags)
        root = _resolve_path(path)
        results = []

        if root.is_file():
            files = [root]
        else:
            files = [
                f for f in root.rglob("*")
                if f.is_file()
                and not any(part.startswith(".") for part in f.parts)
                and f.suffix in {
                    ".py", ".js", ".ts", ".jsx", ".tsx", ".rs", ".go",
                    ".java", ".c", ".cpp", ".h", ".php", ".rb", ".md",
                    ".txt", ".json", ".yaml", ".yml", ".toml", ".html",
                    ".css", ".scss", ".sh", ".env", ".conf",
                }
            ]

        for f in files[:200]:
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
                for i, line in enumerate(text.splitlines(), 1):
                    if compiled.search(line):
                        rel = f.relative_to(CWD) if f.is_relative_to(CWD) else f
                        results.append(f"{rel}:{i}: {line.rstrip()}")
                        if len(results) >= 50:
                            break
            except Exception:
                pass
            if len(results) >= 50:
                break

        if not results:
            return "(no matches)"
        out = "\n".join(results)
        if len(results) == 50:
            out += "\n... [capped at 50 results]"
        return out
    except re.error as exc:
        return f"[error] Bad regex: {exc}"
    except Exception as exc:
        return f"[error] {exc}"


def tool_web_search(query: str, max_results: int = 5) -> str:
    if not DDG_OK:
        return "[error] duckduckgo-search not installed. Run: pip install duckduckgo-search"
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "(no results)"
        lines = []
        for r in results:
            lines.append(f"**{r.get('title', '')}**")
            lines.append(r.get("href", ""))
            lines.append(r.get("body", ""))
            lines.append("")
        return "\n".join(lines).strip()
    except Exception as exc:
        return f"[error] {exc}"


TOOL_EXECUTORS = {
    "bash":        lambda args: tool_bash(**args),
    "read_file":   lambda args: tool_read_file(**args),
    "write_file":  lambda args: tool_write_file(**args),
    "edit_file":   lambda args: tool_edit_file(**args),
    "list_dir":    lambda args: tool_list_dir(**args),
    "glob_search": lambda args: tool_glob_search(**args),
    "grep_search": lambda args: tool_grep_search(**args),
    "web_search":  lambda args: tool_web_search(**args),
}


def execute_tool(name: str, args: dict) -> str:
    executor = TOOL_EXECUTORS.get(name)
    if executor is None:
        return f"[error] Unknown tool: {name}"
    return executor(args)


# ══════════════════════════════════════════════════════════════════════════════
#  LLM BACKENDS
# ══════════════════════════════════════════════════════════════════════════════

class OllamaBackend:
    """
    100% FREE — runs models locally on your machine.
    No API key, no rate limits, never exhausts.
    Requires Ollama installed: https://ollama.com
    """

    def __init__(self, model: str = "qwen3-vl:8b"):
        self.model = model
        self.name = f"ollama/{model}"
        self.cost = "$0.00 (local)"

    @staticmethod
    def list_models() -> list:
        if not OLLAMA_OK:
            return []
        try:
            resp = _ollama_lib.list()
            # SDK v0.6+ returns an object with .models attribute
            models_list = getattr(resp, "models", None)
            if models_list is None:
                # fallback: dict-style
                models_list = resp.get("models", [])
            result = []
            for m in models_list:
                # Each model may be an object or dict
                name = getattr(m, "model", None) or (m.get("model") if isinstance(m, dict) else str(m))
                if name:
                    result.append(name)
            return result
        except Exception:
            return []

    @staticmethod
    def is_running() -> bool:
        try:
            import urllib.request
            urllib.request.urlopen("http://localhost:11434", timeout=2)
            return True
        except Exception:
            return False

    def chat(self, messages: list, tools: list) -> dict:
        """
        Returns:
          {
            "content": str | None,
            "tool_calls": [{"name": str, "arguments": dict, "id": str}],
          }
        """
        # Filter out unsupported keys and rewrite tool_calls to Ollama's
        # expected OpenAI wire format: {id, type, function:{name, arguments}}
        clean_messages = []
        for m in messages:
            cm = {k: v for k, v in m.items()
                  if k in ("role", "content", "tool_calls", "tool_call_id", "name")}
            if cm.get("content") is None:
                cm["content"] = ""
            # Reformat tool_calls from our flat {id,name,arguments} to Ollama's
            # nested {id, type, function:{name,arguments}} structure
            if cm.get("tool_calls"):
                cm["tool_calls"] = [
                    {
                        "id":       tc.get("id", ""),
                        "type":     "function",
                        "function": {
                            "name":      tc["name"],
                            "arguments": tc.get("arguments", {}),
                        },
                    }
                    for tc in cm["tool_calls"]
                ]
            clean_messages.append(cm)

        ollama_tools = [
            {"type": "function", "function": spec["function"]}
            for spec in tools
        ]

        response = _ollama_lib.chat(
            model=self.model,
            messages=clean_messages,
            tools=ollama_tools,
        )

        # SDK v0.6 returns an object; support both object and dict
        msg = getattr(response, "message", None) or response.get("message", {})

        # Extract content
        raw_content = getattr(msg, "content", None)
        if raw_content is None and isinstance(msg, dict):
            raw_content = msg.get("content")

        # Extract tool_calls
        raw_tool_calls = getattr(msg, "tool_calls", None)
        if raw_tool_calls is None and isinstance(msg, dict):
            raw_tool_calls = msg.get("tool_calls")
        raw_tool_calls = raw_tool_calls or []

        tool_calls = []
        for i, tc in enumerate(raw_tool_calls):
            # tc may be object or dict
            fn_obj = getattr(tc, "function", None) or (tc.get("function", {}) if isinstance(tc, dict) else {})
            fn_name = getattr(fn_obj, "name", None) or (fn_obj.get("name", "") if isinstance(fn_obj, dict) else "")
            fn_args = getattr(fn_obj, "arguments", None)
            if fn_args is None and isinstance(fn_obj, dict):
                fn_args = fn_obj.get("arguments", {})
            if isinstance(fn_args, str):
                try:
                    fn_args = json.loads(fn_args)
                except Exception:
                    fn_args = {}
            tool_calls.append({"id": f"call_{i}", "name": fn_name, "arguments": fn_args or {}})

        return {
            "content": raw_content or None,
            "tool_calls": tool_calls,
        }

    def chat_streaming(self, messages: list, tools: list, on_token=None) -> dict:
        """Like chat() but streams text tokens via on_token(token: str) callback.

        Tool calls are still returned in bulk at the end (Ollama limitation).
        If on_token is None, falls back to non-streaming chat().
        """
        if on_token is None:
            return self.chat(messages, tools)

        clean_messages = []
        for m in messages:
            cm = {k: v for k, v in m.items()
                  if k in ("role", "content", "tool_calls", "tool_call_id", "name")}
            if cm.get("content") is None:
                cm["content"] = ""
            if cm.get("tool_calls"):
                cm["tool_calls"] = [
                    {
                        "id":       tc.get("id", ""),
                        "type":     "function",
                        "function": {
                            "name":      tc["name"],
                            "arguments": tc.get("arguments", {}),
                        },
                    }
                    for tc in cm["tool_calls"]
                ]
            clean_messages.append(cm)

        ollama_tools = [
            {"type": "function", "function": spec["function"]}
            for spec in tools
        ]

        content_parts = []
        tool_calls_raw = []

        stream = _ollama_lib.chat(
            model=self.model,
            messages=clean_messages,
            tools=ollama_tools,
            stream=True,
        )

        for chunk in stream:
            msg = getattr(chunk, "message", None) or (chunk.get("message", {}) if isinstance(chunk, dict) else {})

            # Stream text token
            token = getattr(msg, "content", None)
            if token is None and isinstance(msg, dict):
                token = msg.get("content")
            if token:
                content_parts.append(token)
                on_token(token)

            # Collect tool calls (usually in the final chunk)
            raw_tcs = getattr(msg, "tool_calls", None)
            if raw_tcs is None and isinstance(msg, dict):
                raw_tcs = msg.get("tool_calls")
            if raw_tcs:
                tool_calls_raw.extend(raw_tcs)

        # Parse tool calls
        tool_calls = []
        for i, tc in enumerate(tool_calls_raw):
            fn_obj = getattr(tc, "function", None) or (tc.get("function", {}) if isinstance(tc, dict) else {})
            fn_name = getattr(fn_obj, "name", None) or (fn_obj.get("name", "") if isinstance(fn_obj, dict) else "")
            fn_args = getattr(fn_obj, "arguments", None)
            if fn_args is None and isinstance(fn_obj, dict):
                fn_args = fn_obj.get("arguments", {})
            if isinstance(fn_args, str):
                try:
                    fn_args = json.loads(fn_args)
                except Exception:
                    fn_args = {}
            tool_calls.append({"id": f"call_{i}", "name": fn_name, "arguments": fn_args or {}})

        return {
            "content": "".join(content_parts) or None,
            "tool_calls": tool_calls,
        }


class GeminiBackend:
    """
    Google Gemini 2.5 Flash -- free tier: ~1500 req/day.
    Nearly-free paid tier: $0.30 / 1M input tokens.
    Requires: GEMINI_API_KEY env var.
    Get free key at: https://aistudio.google.com
    """

    DEFAULT_MODEL = "gemini-2.5-flash-preview-04-17"

    def __init__(self, model: str = None):
        self.model_name = model or self.DEFAULT_MODEL
        self.name = f"gemini/{self.model_name}"
        self.cost = "Free tier (1500 req/day) or ~$0.30/1M tokens"
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY not set.\n"
                "Get a free key at https://aistudio.google.com\n"
                "Then run: set GEMINI_API_KEY=your_key_here"
            )
        self._client = genai_new.Client(api_key=api_key)

    def chat(self, messages: list, tools: list) -> dict:
        from google.genai import types as genai_types

        # Separate system prompt
        system_text = None
        history = []
        for m in messages:
            role = m["role"]
            content = m.get("content") or ""
            if role == "system":
                system_text = content
            elif role in ("tool",):
                history.append(genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text=f"[Tool result]\n{content}")],
                ))
            elif role == "assistant":
                history.append(genai_types.Content(
                    role="model",
                    parts=[genai_types.Part(text=content)],
                ))
            else:
                history.append(genai_types.Content(
                    role="user",
                    parts=[genai_types.Part(text=content)],
                ))

        # Build tool declarations
        fn_decls = []
        for spec in tools:
            fn = spec["function"]
            props = {}
            for pname, pinfo in fn.get("parameters", {}).get("properties", {}).items():
                props[pname] = genai_types.Schema(
                    type=genai_types.Type.STRING,
                    description=pinfo.get("description", ""),
                )
            fn_decls.append(genai_types.FunctionDeclaration(
                name=fn["name"],
                description=fn.get("description", ""),
                parameters=genai_types.Schema(
                    type=genai_types.Type.OBJECT,
                    properties=props,
                    required=fn.get("parameters", {}).get("required", []),
                ),
            ))

        cfg = genai_types.GenerateContentConfig(
            system_instruction=system_text,
            tools=[genai_types.Tool(function_declarations=fn_decls)] if fn_decls else [],
        )

        response = self._client.models.generate_content(
            model=self.model_name,
            contents=history,
            config=cfg,
        )

        content_text = None
        tool_calls = []
        for part in response.candidates[0].content.parts:
            if getattr(part, "text", None):
                content_text = (content_text or "") + part.text
            fc = getattr(part, "function_call", None)
            if fc and getattr(fc, "name", None):
                tool_calls.append({
                    "id": f"call_{len(tool_calls)}",
                    "name": fc.name,
                    "arguments": dict(fc.args) if fc.args else {},
                })
        return {"content": content_text, "tool_calls": tool_calls}


# ══════════════════════════════════════════════════════════════════════════════
#  AGENT LOOP
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """\
You are Claw, an expert AI coding agent running locally on the user's machine.

You have access to tools to read/write files, run shell commands, search code, \
and browse the web. Use them freely and precisely.

Guidelines:
- Always read existing code before editing it.
- Make targeted, minimal edits. Prefer edit_file over write_file for changes.
- After running bash commands, check exit codes and stderr.
- Be concise — don't repeat what was already said.
- When a task is done, briefly summarize what you changed.
- You are running as a local process with full filesystem access in the working directory.
"""


class Agent:
    def __init__(self, backend, verbose: bool = False):
        self.backend = backend
        self.verbose = verbose
        self.messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.turn_count = 0
        self.session_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    def _print(self, *args, **kwargs):
        if RICH:
            console.print(*args, **kwargs)
        else:
            print(*args, **kwargs)

    def _show_tool_call(self, name: str, args: dict):
        if RICH:
            args_str = json.dumps(args, indent=2)
            console.print(
                Panel(
                    Syntax(args_str, "json", theme="dracula", line_numbers=False),
                    title=f"[bold cyan]🔧 {name}[/]",
                    border_style="cyan",
                    expand=False,
                )
            )
        else:
            print(f"\n[tool] {name}({json.dumps(args)})")

    def _show_tool_result(self, name: str, result: str):
        if not self.verbose and len(result) > 400:
            result = result[:400] + "\n… [truncated, use verbose mode for full output]"
        if RICH:
            console.print(
                Panel(
                    result,
                    title=f"[bold green]✅ {name} result[/]",
                    border_style="green dim",
                    expand=False,
                )
            )
        else:
            print(f"[result] {result}\n")

    def _show_thinking(self):
        if RICH:
            console.print("[dim]🤔 Thinking…[/dim]")

    def _show_assistant_message(self, text: str):
        if RICH:
            console.print(
                Panel(
                    Markdown(text),
                    title="[bold magenta]🦞 Claw[/]",
                    border_style="magenta",
                )
            )
        else:
            print(f"\nClaw: {text}\n")

    def run_turn(self, user_input: str) -> str:
        """Run one full agentic turn (may involve multiple tool calls)."""
        self.turn_count += 1
        self.messages.append({"role": "user", "content": user_input})

        final_text = ""
        max_steps = 20

        for step in range(max_steps):
            self._show_thinking()
            response = self.backend.chat(self.messages, TOOL_SPECS)

            content = response.get("content") or ""
            tool_calls = response.get("tool_calls", [])

            # Append assistant message
            self.messages.append({
                "role": "assistant",
                "content": content,
                "tool_calls": tool_calls,
            })

            if not tool_calls:
                # Agent is done — no more tool calls
                final_text = content
                self._show_assistant_message(content)
                break

            # Execute each tool call
            for tc in tool_calls:
                name = tc["name"]
                args = tc["arguments"]
                self._show_tool_call(name, args)
                result = execute_tool(name, args)
                self._show_tool_result(name, result)

                # Feed result back as a tool message
                self.messages.append({
                    "role": "tool",
                    "content": result,
                    "tool_call_id": tc.get("id", ""),
                    "name": name,
                })

            if content:
                # Agent also said something alongside tool calls
                self._print(f"[dim]{content}[/dim]" if RICH else content)
        else:
            final_text = "[agent] Reached max steps — stopping."
            self._print(final_text)

        return final_text

    def run_turn_streaming(self, user_input: str, event_queue) -> str:
        """Run one agentic turn, pushing SSE event dicts into event_queue.

        Event types pushed to the queue:
          {"type": "thinking"}
          {"type": "token",       "token": str}   ← real-time text (Ollama only)
          {"type": "tool_call",   "name": str, "args": dict}
          {"type": "tool_result", "name": str, "result": str}
          {"type": "done",        "content": str}
          {"type": "error",       "message": str}
        The caller must push None (sentinel) after this returns to close the stream.
        """
        self.turn_count += 1
        self.messages.append({"role": "user", "content": user_input})

        final_text = ""
        max_steps  = 20
        # Check whether backend supports token-level streaming
        supports_streaming = hasattr(self.backend, "chat_streaming")

        for step in range(max_steps):
            event_queue.put({"type": "thinking"})

            if supports_streaming:
                # Stream tokens in real-time; suppress "thinking" after first token
                first_token_sent = [False]

                def _on_token(tok):
                    if not first_token_sent[0]:
                        event_queue.put({"type": "streaming_start"})
                        first_token_sent[0] = True
                    event_queue.put({"type": "token", "token": tok})

                response = self.backend.chat_streaming(
                    self.messages, TOOL_SPECS, on_token=_on_token
                )
            else:
                response = self.backend.chat(self.messages, TOOL_SPECS)

            content    = response.get("content") or ""
            tool_calls = response.get("tool_calls", [])

            self.messages.append({
                "role":       "assistant",
                "content":    content,
                "tool_calls": tool_calls,
            })

            if not tool_calls:
                final_text = content
                event_queue.put({"type": "done", "content": content})
                break

            for tc in tool_calls:
                name = tc["name"]
                args = tc["arguments"]
                event_queue.put({"type": "tool_call", "name": name, "args": args})

                result  = execute_tool(name, args)
                display = result if len(result) <= 3000 else result[:3000] + "\n…[truncated]"
                event_queue.put({"type": "tool_result", "name": name, "result": display})

                self.messages.append({
                    "role":         "tool",
                    "content":      result,
                    "tool_call_id": tc.get("id", ""),
                    "name":         name,
                })

            if content:
                event_queue.put({"type": "interim", "content": content})
        else:
            final_text = "[agent] Reached max steps without completing."
            event_queue.put({"type": "error", "message": final_text})

        return final_text

    def save_session(self):
        path = SESSION_DIR / f"{self.session_id}.json"
        data = {
            "session_id": self.session_id,
            "backend": self.backend.name,
            "turn_count": self.turn_count,
            "messages": self.messages,
            "saved_at": datetime.datetime.now().isoformat(),
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    def load_session(self, path: str):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.messages = data["messages"]
        self.turn_count = data.get("turn_count", 0)
        self.session_id = data.get("session_id", self.session_id)
        return data


# ══════════════════════════════════════════════════════════════════════════════
#  REPL — Interactive loop
# ══════════════════════════════════════════════════════════════════════════════

HELP_TEXT = """\
[bold]🦞 Claw Agent — Commands[/]

  [cyan]/help[/]              Show this help
  [cyan]/status[/]            Show session info + model
  [cyan]/clear[/]             Clear conversation history
  [cyan]/save[/]              Save session to disk
  [cyan]/load <path>[/]       Load a saved session
  [cyan]/sessions[/]          List saved sessions
  [cyan]/model[/]             Show current model
  [cyan]/cwd <path>[/]        Change working directory
  [cyan]/verbose[/]           Toggle verbose tool output
  [cyan]/exit[/]              Quit

  Type any message to chat with the agent.
  The agent can read/write files, run shell commands, and search the web.
"""


def make_backend(model_arg: "str | None") -> "OllamaBackend | GeminiBackend":
    """Auto-select the best available backend."""
    if model_arg == "gemini" or (model_arg and model_arg.startswith("gemini")):
        if not GEMINI_OK:
            print("❌ google-generativeai not installed. Run: pip install google-generativeai")
            sys.exit(1)
        model_name = model_arg if model_arg != "gemini" else None
        return GeminiBackend(model=model_name)

    # Ollama (local, free) — default
    if not OLLAMA_OK:
        print(
            "❌ ollama Python package not found.\n"
            "   Install: pip install ollama\n"
            "   Also install Ollama: https://ollama.com\n"
        )
        sys.exit(1)

    if not OllamaBackend.is_running():
        print(
            "❌ Ollama is not running.\n"
            "   Start it: ollama serve\n"
            "   (or just open the Ollama app)\n"
        )
        sys.exit(1)

    ollama_model = model_arg or "qwen2.5-coder:7b"
    available = OllamaBackend.list_models()

    if not available:
        print(
            f"❌ No models are pulled in Ollama yet.\n"
            f"   Pull one:  ollama pull {ollama_model}\n"
            f"   Then re-run this agent.\n"
        )
        sys.exit(1)

    # If requested model not available, suggest closest or auto-pick
    if ollama_model not in available:
        # Try to find a coding-capable model
        preferred_order = [
            "qwen2.5-coder:7b", "qwen2.5-coder", "qwen2.5-coder:14b",
            "deepseek-coder-v2", "deepseek-coder-v2:16b",
            "codellama", "codellama:13b", "llama3.2", "llama3",
            "mistral", "phi3", "gemma2",
        ]
        chosen = next((m for m in preferred_order if any(m in a for a in available)), available[0])
        print(f"ℹ Model '{ollama_model}' not found. Using '{chosen}' instead.")
        ollama_model = chosen

    return OllamaBackend(model=ollama_model)


def print_banner(backend):
    if RICH:
        console.print(
            Panel(
                f"[bold white]>> CLAW AGENT <<[/]\n"
                f"[dim]AI coding agent built on Claw Code architecture[/]\n\n"
                f"[green]Model:[/]    [cyan]{backend.name}[/]\n"
                f"[green]Cost:[/]     [yellow]{backend.cost}[/]\n"
                f"[green]Work dir:[/] [blue]{CWD}[/]\n\n"
                f"[dim]Type /help for commands. Ctrl+C or /exit to quit.[/]",
                title="[bold magenta]Welcome[/]",
                border_style="magenta",
                expand=False,
            )
        )
    else:
        print(f"\nCLAW AGENT  |  {backend.name}  |  {CWD}\n")


def run_repl(agent: Agent):
    global CWD
    verbose = False

    while True:
        try:
            if RICH:
                user_input = console.input("[bold blue]You ▶ [/]").strip()
            else:
                user_input = input("You > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nBye! 👋")
            break

        if not user_input:
            continue

        # ── Slash commands ──
        if user_input.startswith("/"):
            cmd = user_input.split()[0].lower()
            rest = user_input[len(cmd):].strip()

            if cmd in ("/exit", "/quit", "/q"):
                print("Bye! 👋")
                break

            elif cmd == "/help":
                if RICH:
                    console.print(HELP_TEXT)
                else:
                    print(HELP_TEXT)

            elif cmd == "/status":
                if RICH:
                    tbl = Table(show_header=False, box=None)
                    tbl.add_column("key", style="green")
                    tbl.add_column("val", style="white")
                    tbl.add_row("Model", agent.backend.name)
                    tbl.add_row("Cost", agent.backend.cost)
                    tbl.add_row("Work dir", str(CWD))
                    tbl.add_row("Turn count", str(agent.turn_count))
                    tbl.add_row("Messages", str(len(agent.messages)))
                    tbl.add_row("Session ID", agent.session_id)
                    tbl.add_row("Verbose", str(verbose))
                    console.print(Panel(tbl, title="Status", border_style="cyan"))
                else:
                    print(f"Model: {agent.backend.name} | Dir: {CWD} | Turns: {agent.turn_count}")

            elif cmd == "/clear":
                agent.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                agent.turn_count = 0
                print("✅ Conversation cleared.")

            elif cmd == "/save":
                path = agent.save_session()
                print(f"✅ Session saved to: {path}")

            elif cmd == "/sessions":
                sessions = sorted(SESSION_DIR.glob("*.json"), reverse=True)
                if sessions:
                    for s in sessions[:10]:
                        print(f"  {s}")
                else:
                    print("No saved sessions.")

            elif cmd == "/load":
                if not rest:
                    print("Usage: /load <path>")
                else:
                    try:
                        data = agent.load_session(rest)
                        print(f"✅ Loaded session: {data.get('session_id')} ({data.get('saved_at')})")
                    except Exception as exc:
                        print(f"❌ {exc}")

            elif cmd == "/model":
                print(f"Model: {agent.backend.name}  |  Cost: {agent.backend.cost}")

            elif cmd == "/cwd":
                if rest:
                    new_cwd = Path(rest).expanduser()
                    if new_cwd.is_dir():
                        CWD = new_cwd
                        os.chdir(CWD)
                        print(f"✅ Working dir changed to: {CWD}")
                    else:
                        print(f"❌ Not a directory: {rest}")
                else:
                    print(f"Current dir: {CWD}")

            elif cmd == "/verbose":
                verbose = not verbose
                agent.verbose = verbose
                print(f"Verbose: {'ON' if verbose else 'OFF'}")

            else:
                print(f"Unknown command: {cmd}  (type /help)")
            continue

        # ── Normal chat ──
        try:
            agent.run_turn(user_input)
        except KeyboardInterrupt:
            print("\n[interrupted]")
        except Exception as exc:
            print(f"❌ Error: {exc}")
            if verbose:
                import traceback
                traceback.print_exc()


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Claw Agent -- Free AI coding agent (never exhausts)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python agent.py                          # Interactive REPL
              python agent.py "refactor utils.py"     # One-shot task
              python agent.py --model gemini          # Use Gemini (cloud)
              python agent.py --list-models           # List Ollama models
              python agent.py --model qwen2.5-coder:14b  # Specific local model

            FREE SETUP (Ollama -- never exhausts):
              1. Install Ollama: https://ollama.com/download
              2. Pull a model:   ollama pull qwen2.5-coder:7b
              3. Run agent:      python agent.py
        """),
    )
    parser.add_argument("prompt", nargs="?", help="One-shot prompt (non-interactive)")
    parser.add_argument("--model", "-m", default=None, help="Model to use (ollama/<name> or gemini)")
    parser.add_argument("--list-models", action="store_true", help="List available Ollama models")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose tool output")
    parser.add_argument("--cwd", default=None, help="Set working directory")
    args = parser.parse_args()

    global CWD
    if args.cwd:
        CWD = Path(args.cwd).expanduser().resolve()
        os.chdir(CWD)

    if args.list_models:
        if not OLLAMA_OK:
            print("❌ ollama package not installed: pip install ollama")
            return
        if not OllamaBackend.is_running():
            print("❌ Ollama is not running. Start it with: ollama serve")
            return
        models = OllamaBackend.list_models()
        if models:
            print("Available Ollama models:")
            for m in models:
                print(f"  {m}")
        else:
            print("No models installed. Pull one: ollama pull qwen2.5-coder:7b")
        return

    backend = make_backend(args.model)
    agent = Agent(backend=backend, verbose=args.verbose)

    if args.prompt:
        # One-shot mode
        print_banner(backend)
        agent.run_turn(args.prompt)
    else:
        # Interactive REPL
        print_banner(backend)
        run_repl(agent)


if __name__ == "__main__":
    main()
