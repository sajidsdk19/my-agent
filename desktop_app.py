#!/usr/bin/env python3
"""
Claw Agent — Windows Desktop Application
Powered by CustomTkinter. Talks directly to the Agent class (no browser needed).

Run:  python desktop_app.py
"""
import sys
import os
import threading
import queue
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import customtkinter as ctk
from agent import (
    Agent, make_backend, OllamaBackend,
    OLLAMA_OK, GEMINI_OK, SYSTEM_PROMPT,
)

# ── Design Tokens ──────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

BG      = "#09090f"
SURF    = "#111318"
S2      = "#181b24"
S3      = "#1f2330"
BORDER  = "#252836"
TEXT    = "#dde1ee"
MUTED   = "#7a7f9a"
DIM     = "#3a3f55"
ACCENT  = "#9d70ff"
CYAN    = "#3dd6f5"
GREEN   = "#56d17b"
YELLOW  = "#f0a742"
RED     = "#ff5f57"

F_BODY  = ("Inter", 13)
F_SMALL = ("Inter", 11)
F_MONO  = ("JetBrains Mono", 11)
F_TITLE = ("Inter", 15, "bold")

TOOL_ICONS = {
    "bash": "💻", "read_file": "📖", "write_file": "📝",
    "edit_file": "✏️", "list_dir": "📁", "glob_search": "🔎",
    "grep_search": "🔍", "web_search": "🌐",
}


# ══════════════════════════════════════════════════════════════════════════════
#  Sidebar
# ══════════════════════════════════════════════════════════════════════════════
class Sidebar(ctk.CTkFrame):
    def __init__(self, master, on_model_change, on_clear, on_save, **kw):
        super().__init__(master, width=260, fg_color=SURF, corner_radius=0, **kw)
        self.grid_propagate(False)
        self.on_model_change = on_model_change

        r = 0

        # Logo
        logo = ctk.CTkFrame(self, fg_color="transparent")
        logo.grid(row=r, column=0, padx=16, pady=(20, 14), sticky="ew"); r += 1
        ctk.CTkLabel(logo, text="🦞  Claw Agent", font=("Inter", 16, "bold"),
                     text_color=ACCENT).pack(anchor="w")
        ctk.CTkLabel(logo, text="AI Coding Assistant", font=F_SMALL,
                     text_color=MUTED).pack(anchor="w")

        self._sep(r); r += 1

        # Model
        self._section_label("MODEL", r); r += 1
        self.model_var = ctk.StringVar(value="Loading…")
        self.model_menu = ctk.CTkOptionMenu(
            self, variable=self.model_var, values=["Loading…"],
            fg_color=S2, button_color=S3, button_hover_color=BORDER,
            text_color=TEXT, font=F_SMALL, width=232,
            command=self._model_changed,
        )
        self.model_menu.grid(row=r, column=0, padx=14, pady=(0, 4), sticky="ew"); r += 1
        self.badge = ctk.CTkLabel(self, text="", font=F_SMALL, text_color=GREEN)
        self.badge.grid(row=r, column=0, padx=16, pady=(0, 12), sticky="w"); r += 1

        self._sep(r); r += 1

        # Session
        self._section_label("SESSION", r); r += 1
        ctk.CTkButton(self, text="💾  Save session", font=F_SMALL, height=32,
                      fg_color=S2, hover_color=S3, text_color=TEXT,
                      command=on_save).grid(row=r, column=0, padx=14, pady=(0, 6), sticky="ew"); r += 1
        ctk.CTkButton(self, text="🗑  Clear conversation", font=F_SMALL, height=32,
                      fg_color=S2, hover_color="#281414", text_color=RED,
                      command=on_clear).grid(row=r, column=0, padx=14, pady=(0, 12), sticky="ew"); r += 1

        self._sep(r); r += 1

        # Status
        self._section_label("STATUS", r); r += 1
        stat = ctk.CTkFrame(self, fg_color=S2, corner_radius=8)
        stat.grid(row=r, column=0, padx=14, pady=(0, 12), sticky="ew"); r += 1
        stat.grid_columnconfigure(1, weight=1)
        self.s_model  = self._stat(stat, "Model",  "—", 0)
        self.s_turns  = self._stat(stat, "Turns",  "0", 1)
        self.s_status = self._stat(stat, "Status", "Idle", 2)

        self._sep(r); r += 1

        # CWD
        self._section_label("WORKING DIR", r); r += 1
        self.cwd_lbl = ctk.CTkLabel(self, text=str(Path.cwd()),
                                    font=("JetBrains Mono", 9), text_color=MUTED,
                                    wraplength=232, justify="left", anchor="w")
        self.cwd_lbl.grid(row=r, column=0, padx=16, pady=(0, 12), sticky="w"); r += 1

        # Spacer + footer
        self.grid_rowconfigure(r, weight=1); r += 1
        ctk.CTkLabel(self, text="Built on Claw Code architecture",
                     font=("Inter", 9), text_color=DIM
                     ).grid(row=r, column=0, padx=16, pady=(0, 14), sticky="s")

    def _sep(self, row):
        ctk.CTkFrame(self, height=1, fg_color=BORDER
                     ).grid(row=row, column=0, sticky="ew", padx=10)

    def _section_label(self, text, row):
        ctk.CTkLabel(self, text=text, font=("Inter", 9, "bold"), text_color=DIM
                     ).grid(row=row, column=0, padx=16, pady=(12, 4), sticky="w")

    def _stat(self, parent, key, val, row):
        ctk.CTkLabel(parent, text=key, font=F_SMALL, text_color=MUTED
                     ).grid(row=row, column=0, padx=12, pady=(5, 2), sticky="w")
        lbl = ctk.CTkLabel(parent, text=val, font=F_MONO, text_color=TEXT)
        lbl.grid(row=row, column=1, padx=12, pady=(5, 2), sticky="e")
        return lbl

    def set_models(self, models):
        if not models:
            self.model_menu.configure(values=["No models found"])
            self.model_var.set("No models found")
            self.badge.configure(text="⚠ Start Ollama or set GEMINI_API_KEY",
                                 text_color=YELLOW)
            return
        self.model_menu.configure(values=models)
        self.model_var.set(models[0])
        self._model_changed(models[0])

    def _model_changed(self, model):
        is_free = "gemini" not in model
        self.badge.configure(
            text="🟢 Local · Free" if is_free else "☁️ Cloud",
            text_color=GREEN if is_free else CYAN,
        )
        self.on_model_change(model)

    def update_status(self, agent=None, busy=False):
        self.s_status.configure(
            text="Busy" if busy else "Idle",
            text_color=YELLOW if busy else GREEN,
        )
        if agent:
            self.s_model.configure(text=agent.backend.name.split("/")[-1][:22])
            self.s_turns.configure(text=str(agent.turn_count))


# ══════════════════════════════════════════════════════════════════════════════
#  Chat Area
# ══════════════════════════════════════════════════════════════════════════════
class ChatArea(ctk.CTkScrollableFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color=BG, corner_radius=0, **kw)
        self.grid_columnconfigure(0, weight=1)
        self._row = 0
        self._thinking_widget = None
        self._thinking_lbl    = None
        self._streaming_lbl   = None
        self._streaming_text  = ""
        self._anim_step       = 0
        self._show_welcome()

    # ── Welcome ──────────────────────────────────────────────────────────────
    def _show_welcome(self):
        self._welcome = ctk.CTkFrame(self, fg_color="transparent")
        self._welcome.grid(row=self._next(), column=0, pady=50, padx=40, sticky="ew")
        self._welcome.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self._welcome, text="🦞", font=("Inter", 56)).grid(pady=(0, 10))
        ctk.CTkLabel(self._welcome, text="Hello! I'm Claw",
                     font=("Inter", 22, "bold"), text_color=TEXT).grid(pady=(0, 8))
        ctk.CTkLabel(self._welcome,
                     text="Your local AI coding assistant.\nI can read & write files, "
                          "run shell commands, search your code, and browse the web.",
                     font=F_BODY, text_color=MUTED, justify="center").grid(pady=(0, 4))

    def _dismiss_welcome(self):
        if self._welcome and self._welcome.winfo_exists():
            self._welcome.grid_remove()

    # ── Core helpers ─────────────────────────────────────────────────────────
    def _next(self):
        r = self._row; self._row += 1; return r

    def _scroll_bottom(self):
        self.after(60, lambda: self._parent_canvas.yview_moveto(1.0))

    # ── User bubble ──────────────────────────────────────────────────────────
    def append_user(self, text):
        self._dismiss_welcome()
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.grid(row=self._next(), column=0, sticky="ew", padx=20, pady=(0, 10))
        wrap.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(wrap, text="You", font=("Inter", 10, "bold"),
                     text_color=ACCENT).grid(row=0, column=0, sticky="e", padx=(0, 6))
        h = min(max(text.count("\n") * 22 + 46, 46), 220)
        box = ctk.CTkTextbox(wrap, height=h, font=F_BODY, text_color=TEXT,
                             fg_color="#1a1030", border_width=1,
                             border_color="#4a3880", corner_radius=12,
                             wrap="word", activate_scrollbars=False)
        box.insert("1.0", text)
        box.configure(state="disabled")
        box.grid(row=1, column=0, sticky="e", ipadx=4, ipady=2)
        self._scroll_bottom()

    # ── Thinking row ─────────────────────────────────────────────────────────
    def show_thinking(self):
        if self._thinking_widget:
            return
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.grid(row=self._next(), column=0, sticky="ew", padx=20, pady=(0, 6))
        wrap.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(wrap, text="Claw", font=("Inter", 10, "bold"),
                     text_color="#7a5ccc").grid(row=0, column=0, sticky="w", padx=(4, 0))
        lbl = ctk.CTkLabel(wrap, text="⠿ Thinking…", font=F_BODY,
                           text_color=MUTED, fg_color=S2, corner_radius=10,
                           padx=14, pady=9, anchor="w")
        lbl.grid(row=1, column=0, sticky="w")
        self._thinking_widget = wrap
        self._thinking_lbl    = lbl
        self._anim_step = 0
        self._animate_thinking()
        self._scroll_bottom()

    def _animate_thinking(self):
        frames = ["⠿", "⠷", "⠯", "⠟", "⠻", "⠽", "⠾"]
        if self._thinking_lbl and self._thinking_lbl.winfo_exists():
            self._anim_step = (self._anim_step + 1) % len(frames)
            self._thinking_lbl.configure(text=f"{frames[self._anim_step]} Thinking…")
            self.after(220, self._animate_thinking)

    def remove_thinking(self):
        if self._thinking_widget:
            try:
                self._thinking_widget.destroy()
            except Exception:
                pass
            self._thinking_widget = None
            self._thinking_lbl    = None

    # ── Streaming bubble (token by token) ────────────────────────────────────
    def start_streaming(self):
        self.remove_thinking()
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.grid(row=self._next(), column=0, sticky="ew", padx=20, pady=(0, 10))
        wrap.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(wrap, text="Claw", font=("Inter", 10, "bold"),
                     text_color="#7a5ccc").grid(row=0, column=0, sticky="w", padx=(4, 0))
        self._streaming_lbl = ctk.CTkLabel(
            wrap, text="", font=F_BODY, text_color=TEXT,
            fg_color=S2, corner_radius=12, wraplength=680,
            justify="left", padx=14, pady=10, anchor="w",
        )
        self._streaming_lbl.grid(row=1, column=0, sticky="w")
        self._streaming_text = ""

    def append_token(self, tok):
        self._streaming_text += tok
        if self._streaming_lbl and self._streaming_lbl.winfo_exists():
            self._streaming_lbl.configure(text=self._streaming_text)
        self._scroll_bottom()

    def finalize_streaming(self, full_text):
        if self._streaming_lbl and self._streaming_lbl.winfo_exists():
            self._streaming_lbl.configure(text=full_text)
        self._streaming_lbl = None
        self._streaming_text = ""
        self._scroll_bottom()

    # ── Assistant final bubble (non-streaming) ───────────────────────────────
    def append_assistant(self, text):
        self.remove_thinking()
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.grid(row=self._next(), column=0, sticky="ew", padx=20, pady=(0, 10))
        wrap.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(wrap, text="Claw", font=("Inter", 10, "bold"),
                     text_color="#7a5ccc").grid(row=0, column=0, sticky="w", padx=(4, 0))
        lbl = ctk.CTkLabel(wrap, text=text, font=F_BODY, text_color=TEXT,
                           fg_color=S2, corner_radius=12, wraplength=680,
                           justify="left", padx=14, pady=10, anchor="w")
        lbl.grid(row=1, column=0, sticky="w")
        self._scroll_bottom()

    # ── Tool card ─────────────────────────────────────────────────────────────
    def append_tool_card(self, name, args):
        icon    = TOOL_ICONS.get(name, "🔧")
        preview = self._tool_preview(name, args)
        card = ctk.CTkFrame(self, fg_color=S2, corner_radius=8,
                            border_width=1, border_color=BORDER)
        card.grid(row=self._next(), column=0, sticky="ew", padx=20, pady=(0, 5))
        card.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(card, text=icon, font=("Inter", 14)
                     ).grid(row=0, column=0, padx=(10, 5), pady=8, sticky="w")
        ctk.CTkLabel(card, text=name, font=("JetBrains Mono", 11, "bold"),
                     text_color=TEXT).grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(card, text=preview[:70], font=("JetBrains Mono", 10),
                     text_color=MUTED).grid(row=0, column=2, padx=(8, 8), sticky="w")
        pill = ctk.CTkLabel(card, text="⏳ Running", font=("Inter", 10),
                            text_color=YELLOW)
        pill.grid(row=0, column=3, padx=(0, 12), sticky="e")
        self._scroll_bottom()
        return pill

    def update_tool_card(self, pill):
        try:
            pill.configure(text="✅ Done", text_color=GREEN)
        except Exception:
            pass

    # ── Error bubble ─────────────────────────────────────────────────────────
    def append_error(self, msg):
        self.remove_thinking()
        lbl = ctk.CTkLabel(self, text=f"❌  {msg}", font=F_BODY,
                           text_color=RED, fg_color="#1a0808",
                           corner_radius=8, padx=14, pady=9,
                           wraplength=680, justify="left", anchor="w")
        lbl.grid(row=self._next(), column=0, sticky="ew", padx=20, pady=(0, 8))
        self._scroll_bottom()

    def clear(self):
        for w in self.winfo_children():
            w.destroy()
        self._row = 0
        self._thinking_widget = None
        self._thinking_lbl    = None
        self._streaming_lbl   = None
        self._show_welcome()

    @staticmethod
    def _tool_preview(name, args):
        if name == "bash":               return args.get("command", "")
        if name in ("read_file", "write_file", "edit_file"): return args.get("path", "")
        if name == "web_search":         return args.get("query", "")
        if name in ("grep_search", "glob_search"): return args.get("pattern", "")
        if name == "list_dir":           return args.get("path", ".")
        return str(args)[:60]


# ══════════════════════════════════════════════════════════════════════════════
#  Main Application Window
# ══════════════════════════════════════════════════════════════════════════════
class ClawApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Claw Agent")
        self.geometry("1300x820")
        self.minsize(940, 620)
        self.configure(fg_color=BG)

        self.agent       = None
        self.event_queue = queue.Queue()
        self.busy        = False
        self._cur_pill   = None   # tool card pill being updated

        self._build_layout()
        self._load_models()
        self.after(80, self._poll_events)

    # ── Build layout ─────────────────────────────────────────────────────────
    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar = Sidebar(
            self,
            on_model_change=self._on_model_change,
            on_clear=self._clear_chat,
            on_save=self._save_session,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        # Right pane
        right = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # Header bar
        hdr = ctk.CTkFrame(right, fg_color=SURF, height=50, corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)
        hdr.grid_propagate(False)
        ctk.CTkLabel(hdr, text="🦞 Claw Agent", font=F_TITLE,
                     text_color=TEXT).grid(row=0, column=0, padx=20, pady=13, sticky="w")
        self.status_lbl = ctk.CTkLabel(hdr, text="● Idle", font=F_SMALL,
                                       text_color=GREEN)
        self.status_lbl.grid(row=0, column=1, padx=20, pady=13, sticky="e")

        # Chat area
        self.chat = ChatArea(right)
        self.chat.grid(row=1, column=0, sticky="nsew")

        # Input area
        inp = ctk.CTkFrame(right, fg_color=SURF, height=88, corner_radius=0)
        inp.grid(row=2, column=0, sticky="ew")
        inp.grid_columnconfigure(0, weight=1)
        inp.grid_propagate(False)

        box = ctk.CTkFrame(inp, fg_color=S2, corner_radius=14)
        box.grid(row=0, column=0, padx=16, pady=(14, 6), sticky="ew", columnspan=2)
        box.grid_columnconfigure(0, weight=1)

        self.input_box = ctk.CTkTextbox(
            box, height=48, font=F_BODY, text_color=TEXT,
            fg_color="transparent", border_width=0, wrap="word",
        )
        self.input_box.grid(row=0, column=0, padx=(14, 6), pady=6, sticky="ew")
        self.input_box.bind("<Return>", self._on_enter)
        self.input_box.bind("<Shift-Return>", lambda e: None)  # allow native newline insertion

        self.send_btn = ctk.CTkButton(
            box, text="➤", width=46, height=46, font=("Inter", 16, "bold"),
            fg_color=ACCENT, hover_color="#8058ee", text_color="white",
            corner_radius=11, command=self._send,
        )
        self.send_btn.grid(row=0, column=1, padx=(0, 8), pady=6)

        ctk.CTkLabel(inp, text="Enter to send · Shift+Enter for new line",
                     font=("Inter", 9), text_color=DIM
                     ).grid(row=1, column=0, padx=20, pady=(0, 6), sticky="e", columnspan=2)

    # ── Model loading ─────────────────────────────────────────────────────────
    def _load_models(self):
        def fetch():
            models = []
            if OLLAMA_OK and OllamaBackend.is_running():
                models += OllamaBackend.list_models()
            has_key = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
            if GEMINI_OK and has_key:
                models.append("gemini")
            self.after(0, self.sidebar.set_models, models)
        threading.Thread(target=fetch, daemon=True).start()

    def _on_model_change(self, model):
        if self.agent:
            # Preserve conversation history across model switches
            self._old_messages = list(self.agent.messages)
            self._old_turns = self.agent.turn_count
        self.agent = None   # force recreate on next send

    def _ensure_agent(self, model):
        if self.agent is None:
            if model in ("No models found", "Loading…", ""):
                raise RuntimeError("No model available. Is Ollama running?")
            try:
                backend = make_backend(model)
                self.agent = Agent(backend=backend)
                # Restore history if we just switched models
                if hasattr(self, "_old_messages"):
                    self.agent.messages = self._old_messages
                    self.agent.turn_count = self._old_turns
                    del self._old_messages
                    del self._old_turns
            except SystemExit:
                raise RuntimeError("Failed to start backend. Check Ollama is running.")

    # ── Send message ──────────────────────────────────────────────────────────
    def _on_enter(self, event):
        # Allow Shift+Enter for newlines
        if event.state & 0x0001:
            return None
        self._send()
        return "break"

    def _send(self):
        if self.busy:
            return
        text = self.input_box.get("1.0", "end").strip()
        if not text:
            return
        self.input_box.delete("1.0", "end")
        model = self.sidebar.model_var.get()
        self.chat.append_user(text)
        self._set_busy(True)

        def run():
            try:
                self._ensure_agent(model)
                self.agent.run_turn_streaming(text, self.event_queue)
            except Exception as exc:
                self.event_queue.put({"type": "error", "message": str(exc)})
            finally:
                self.event_queue.put(None)   # sentinel

        threading.Thread(target=run, daemon=True).start()

    # ── Poll event queue every 50 ms ──────────────────────────────────────────
    def _poll_events(self):
        try:
            while True:
                ev = self.event_queue.get_nowait()

                if ev is None:                          # sentinel
                    self._set_busy(False)
                    self.sidebar.update_status(self.agent, busy=False)
                    break

                t = ev.get("type")

                if t == "thinking":
                    self.chat.show_thinking()

                elif t == "streaming_start":
                    self.chat.start_streaming()
                    self.status_lbl.configure(text="● Streaming…", text_color=CYAN)

                elif t == "token":
                    self.chat.append_token(ev["token"])

                elif t == "tool_call":
                    self.chat.remove_thinking()
                    self._cur_pill = self.chat.append_tool_card(ev["name"], ev["args"])

                elif t == "tool_result":
                    if self._cur_pill:
                        self.chat.update_tool_card(self._cur_pill)
                        self._cur_pill = None

                elif t == "done":
                    content = ev.get("content", "(no response)")
                    if self.chat._streaming_lbl:
                        self.chat.finalize_streaming(content)
                    else:
                        self.chat.append_assistant(content)

                elif t == "error":
                    self.chat.append_error(ev.get("message", "Unknown error"))
                    self._set_busy(False)

        except queue.Empty:
            pass

        self.after(50, self._poll_events)

    # ── Helpers ──────────────────────────────────────────────────────────────
    def _set_busy(self, b):
        self.busy = b
        self.send_btn.configure(state="disabled" if b else "normal")
        self.status_lbl.configure(
            text="● Thinking…" if b else "● Idle",
            text_color=YELLOW if b else GREEN,
        )
        self.sidebar.update_status(self.agent, busy=b)

    def _clear_chat(self):
        self.chat.clear()
        if self.agent:
            self.agent.messages   = [{"role": "system", "content": SYSTEM_PROMPT}]
            self.agent.turn_count = 0
        self.sidebar.update_status(self.agent)

    def _save_session(self):
        if not self.agent:
            self.chat.append_error("No active session to save.")
            return
        path = self.agent.save_session()
        self.chat.append_assistant(f"✅ Session saved to:\n{path}")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n  🦞  Claw Agent Desktop")
    print("  Starting…\n")
    app = ClawApp()
    app.mainloop()
