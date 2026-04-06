#!/usr/bin/env python3
"""
Claw Agent — Windows Desktop Application
Powered by CustomTkinter. Talks directly to the Agent class (no browser needed).

Run:  python desktop_app.py

Author  : Sajid Khan  –  CTO, TechScape
Website : https://sajidkhan.me
GitHub  : https://github.com/sajidsdk19
"""
import sys
import os
import re
import threading
import queue
from pathlib import Path
import tkinter.font as tkfont
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox
import tkinter.simpledialog as simpledialog

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
    "edit_file": "✏️", "list_dir": "📁", "glob_search": "🖎",
    "grep_search": "🔍", "web_search": "🌐",
}

# File-type icons for the explorer
FILE_ICONS = {
    ".py": "🐍", ".js": "🟡", ".ts": "🟦", ".jsx": "🟡", ".tsx": "🟦",
    ".html": "🌐", ".css": "🎨", ".json": "📎", ".md": "📝",
    ".cs": "🟣", ".cpp": "🟠", ".c": "🟠", ".h": "🟠",
    ".rs": "🪤", ".go": "🟦", ".java": "☕",
    ".sh": "💫", ".bat": "💫", ".yaml": "📌", ".yml": "📌",
    ".txt": "📄", ".env": "🔒", ".toml": "📌", ".ini": "📌",
}


# ══════════════════════════════════════════════════════════════════════════════
#  Sidebar
# ══════════════════════════════════════════════════════════════════════════════
class Sidebar(ctk.CTkFrame):
    def __init__(self, master, on_model_change, on_clear, on_save, on_refresh, **kw):
        super().__init__(master, width=260, fg_color=SURF, corner_radius=0, **kw)
        self.grid_propagate(False)
        self.on_model_change = on_model_change
        self.on_refresh = on_refresh

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

        # Model row: dropdown + refresh button side by side
        model_row = ctk.CTkFrame(self, fg_color="transparent")
        model_row.grid(row=r, column=0, padx=14, pady=(0, 4), sticky="ew"); r += 1
        model_row.grid_columnconfigure(0, weight=1)

        self.model_var = ctk.StringVar(value="Loading…")
        self.model_menu = ctk.CTkOptionMenu(
            model_row, variable=self.model_var, values=["Loading…"],
            fg_color=S2, button_color=S3, button_hover_color=BORDER,
            text_color=TEXT, font=F_SMALL,
            command=self._model_changed,
        )
        self.model_menu.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        self.refresh_btn = ctk.CTkButton(
            model_row, text="🔄", width=34, height=28,
            fg_color=S3, hover_color=BORDER, text_color=TEXT,
            font=("Inter", 13), corner_radius=7,
            command=self.refresh_models,
        )
        self.refresh_btn.grid(row=0, column=1, sticky="e")

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
        # Default to Desktop; will be updated by explorer callbacks
        _default_cwd = str(Path.home() / "Desktop")
        self.cwd_lbl = ctk.CTkLabel(self, text=_default_cwd,
                                    font=("JetBrains Mono", 9), text_color=MUTED,
                                    wraplength=232, justify="left", anchor="w")
        self.cwd_lbl.grid(row=r, column=0, padx=16, pady=(0, 12), sticky="w"); r += 1

        # Spacer + footer
        self.grid_rowconfigure(r, weight=1); r += 1
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=r, column=0, padx=16, pady=(0, 14), sticky="s")
        ctk.CTkLabel(footer, text="Built on Claw Code architecture",
                     font=("Inter", 9), text_color=DIM).pack(anchor="center")
        ctk.CTkLabel(footer, text="✦  Sajid Khan · CTO TechScape",
                     font=("Inter", 9, "bold"), text_color=ACCENT).pack(anchor="center")
        ctk.CTkLabel(footer, text="sajidkhan.me  ·  github.com/sajidsdk19",
                     font=("Inter", 8), text_color=MUTED).pack(anchor="center")

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

    def set_models(self, models, *, keep_selection=False):
        """Update the model dropdown. If keep_selection is True, preserve current choice."""
        current = self.model_var.get()
        if not models:
            self.model_menu.configure(values=["No models found"])
            self.model_var.set("No models found")
            self.badge.configure(text="⚠ Start Ollama or set GEMINI_API_KEY",
                                 text_color=YELLOW)
            return
        self.model_menu.configure(values=models)
        # Keep existing selection if still available after refresh
        if keep_selection and current in models:
            self.model_var.set(current)
            self._model_changed(current)
        else:
            self.model_var.set(models[0])
            self._model_changed(models[0])

    def refresh_models(self, keep_selection=True):
        """Trigger a live re-query of Ollama models."""
        self.refresh_btn.configure(text="⏳", state="disabled")
        self.on_refresh(keep_selection=keep_selection,
                        done_cb=lambda: self.refresh_btn.configure(text="🔄", state="normal"))

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
        elif agent is None and not hasattr(self, '_model_manually_set'):
            # If no agent yet, show dash only if we haven't manually set it already
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  File Explorer
# ══════════════════════════════════════════════════════════════════════════════
class FileExplorer(ctk.CTkFrame):
    """Left-side file tree panel."""

    def __init__(self, master, on_open_file, on_cwd_change=None, **kw):
        super().__init__(master, fg_color=SURF, corner_radius=0, **kw)
        self.on_open_file = on_open_file   # callback(path: Path)
        self.on_cwd_change = on_cwd_change # callback(path: Path) — called when CWD changes
        self._root_path: Path | None = None
        self._expanded: set[Path] = set()
        self._build()

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Header
        hdr = ctk.CTkFrame(self, fg_color=S2, corner_radius=0, height=42)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)
        hdr.grid_propagate(False)
        ctk.CTkLabel(hdr, text="📂  EXPLORER", font=("Inter", 9, "bold"),
                     text_color=DIM).grid(row=0, column=0, padx=12, pady=0, sticky="w")
        ctk.CTkButton(hdr, text="📂 Open", width=60, height=26,
                      font=F_SMALL, fg_color=S3, hover_color=BORDER,
                      text_color=TEXT, corner_radius=6,
                      command=self.open_folder
                      ).grid(row=0, column=1, padx=(0, 6), pady=8, sticky="e")

        # ── Tree scrollable area
        self._tree = ctk.CTkScrollableFrame(self, fg_color=SURF, corner_radius=0)
        self._tree.grid(row=1, column=0, sticky="nsew")
        self._tree.grid_columnconfigure(0, weight=1)

        # Empty state label
        self._empty_lbl = ctk.CTkLabel(
            self._tree,
            text="No folder open\n\nClick \"Open\" above",
            font=F_SMALL, text_color=DIM, justify="center",
        )
        self._empty_lbl.grid(row=0, column=0, pady=60)

        # ── Footer toolbar
        foot = ctk.CTkFrame(self, fg_color=S2, corner_radius=0, height=38)
        foot.grid(row=2, column=0, sticky="ew")
        foot.grid_propagate(False)
        for i, (label, cmd) in enumerate([
            ("+ File",   self._new_file),
            ("+ Folder", self._new_folder),
        ]):
            ctk.CTkButton(foot, text=label, width=72, height=26,
                          font=F_SMALL, fg_color=S3, hover_color=BORDER,
                          text_color=TEXT, corner_radius=6,
                          command=cmd).grid(row=0, column=i, padx=(6 if i == 0 else 2, 2), pady=6)

    # ── Public API
    def open_folder(self, path: Path | None = None):
        if path is None:
            chosen = filedialog.askdirectory(title="Open Folder")
            if not chosen:
                return
            path = Path(chosen)
        self._root_path = path
        self._expanded = {path}
        self._refresh_tree()
        # Notify app of CWD change
        if self.on_cwd_change:
            self.on_cwd_change(path)

    # ── Tree rendering
    def _refresh_tree(self):
        for w in self._tree.winfo_children():
            w.destroy()
        if self._root_path is None:
            self._empty_lbl = ctk.CTkLabel(
                self._tree, text="No folder open\n\nClick \"Open\" above",
                font=F_SMALL, text_color=DIM, justify="center")
            self._empty_lbl.grid(row=0, column=0, pady=60)
            return
        self._render_dir(self._root_path, depth=0, row_ref=[0])

    def _render_dir(self, path: Path, depth: int, row_ref: list):
        try:
            entries = sorted(path.iterdir(),
                             key=lambda p: (p.is_file(), p.name.lower()))
        except PermissionError:
            return

        for entry in entries:
            row = row_ref[0]
            row_ref[0] += 1
            indent = depth * 16 + 8

            if entry.is_dir():
                arrow = "▾ " if entry in self._expanded else "▸ "
                btn = ctk.CTkButton(
                    self._tree,
                    text=f"{arrow}📁  {entry.name}",
                    anchor="w", font=F_SMALL,
                    fg_color="transparent", hover_color=S3,
                    text_color=TEXT, corner_radius=4, height=26,
                    command=lambda p=entry: self._toggle_dir(p),
                )
                btn.grid(row=row, column=0, sticky="ew",
                         padx=(indent, 4), pady=1)
                self._bind_context(btn, entry)

                if entry in self._expanded:
                    self._render_dir(entry, depth + 1, row_ref)
            else:
                icon = FILE_ICONS.get(entry.suffix.lower(), "📄")
                btn = ctk.CTkButton(
                    self._tree,
                    text=f"{icon}  {entry.name}",
                    anchor="w", font=F_SMALL,
                    fg_color="transparent", hover_color=S3,
                    text_color=MUTED, corner_radius=4, height=24,
                    command=lambda p=entry: self.on_open_file(p),
                )
                btn.grid(row=row, column=0, sticky="ew",
                         padx=(indent, 4), pady=1)
                self._bind_context(btn, entry)

    def _toggle_dir(self, path: Path):
        if path in self._expanded:
            self._expanded.discard(path)
        else:
            self._expanded.add(path)
        self._refresh_tree()

    # ── Context menu (right-click)
    def _bind_context(self, widget, path: Path):
        menu = tk.Menu(widget, tearoff=0, bg=S2, fg=TEXT,
                       activebackground=ACCENT, activeforeground="white",
                       font=("Inter", 11))
        menu.add_command(label="🔍 Open",
                         command=lambda: self.on_open_file(path) if path.is_file() else None)
        menu.add_separator()
        menu.add_command(label="✏️  Rename",
                         command=lambda p=path: self._rename(p))
        menu.add_command(label="🗑️  Delete",
                         command=lambda p=path: self._delete(p))

        def show_menu(e):
            try:
                menu.tk_popup(e.x_root, e.y_root)
            finally:
                menu.grab_release()

        widget.bind("<Button-3>", show_menu)

    # ── Toolbar actions
    def _new_file(self):
        parent = self._pick_parent()
        if parent is None:
            return
        name = simpledialog.askstring("New File", "File name:", parent=self)
        if not name:
            return
        p = parent / name
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch(exist_ok=True)
            self._expanded.add(parent)
            self._refresh_tree()
            self.on_open_file(p)
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self)

    def _new_folder(self):
        parent = self._pick_parent()
        if parent is None:
            return
        name = simpledialog.askstring("New Folder", "Folder name:", parent=self)
        if not name:
            return
        p = parent / name
        try:
            p.mkdir(parents=True, exist_ok=True)
            self._expanded.add(parent)
            self._expanded.add(p)
            self._refresh_tree()
            # Notify app: CWD moves into the newly created folder
            if self.on_cwd_change:
                self.on_cwd_change(p)
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self)

    def _pick_parent(self) -> Path | None:
        """Return the root path (or ask user to open one)."""
        if self._root_path is None:
            self.open_folder()
        return self._root_path

    def _rename(self, path: Path):
        new_name = simpledialog.askstring(
            "Rename", f"New name for {path.name}:",
            initialvalue=path.name, parent=self)
        if not new_name or new_name == path.name:
            return
        new_path = path.parent / new_name
        try:
            path.rename(new_path)
            self._refresh_tree()
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self)

    def _delete(self, path: Path):
        if not messagebox.askyesno(
                "Delete",
                f"Delete {'folder' if path.is_dir() else 'file'} \"{path.name}\"?",
                parent=self):
            return
        try:
            if path.is_dir():
                import shutil
                shutil.rmtree(path)
            else:
                path.unlink()
            self._refresh_tree()
        except Exception as exc:
            messagebox.showerror("Error", str(exc), parent=self)


# ══════════════════════════════════════════════════════════════════════════════
#  Syntax Highlighter
# ══════════════════════════════════════════════════════════════════════════════
class SyntaxHighlighter:
    """
    Token-regex syntax highlighter for tk.Text.
    Covers Python, JS/TS, C/C++/C#, Go, Rust, Java, HTML, CSS, JSON, Bash, Markdown.
    Uses a Material Ocean-inspired dark palette to match the app theme.
    """

    # ── Material Ocean palette — matches the dark BG perfectly ───────────────
    _C = {
        "keyword":   "#c792ea",   # purple  — def class if for return
        "keyword2":  "#89ddff",   # sky     — True None self and
        "string":    "#c3e88d",   # lime    — \"string\" 'string'
        "comment":   "#546e7a",   # slate   — # // /* */
        "number":    "#f78c6c",   # orange  — 42  3.14  0xff
        "function":  "#82aaff",   # blue    — fn definitions + calls
        "class_":    "#ffcb6b",   # amber   — ClassName
        "decorator": "#f07178",   # coral   — @decorator  #[attr]
        "operator":  "#89ddff",   # sky     — = + - * / == !=
        "builtin":   "#82aaff",   # blue    — print len range
        "constant":  "#f78c6c",   # orange  — UPPER_CASE
        "tag":       "#f07178",   # coral   — HTML <tag>
        "attr":      "#c792ea",   # purple  — HTML attr=
        "selector":  "#f07178",   # coral   — CSS .selector
        "property":  "#82aaff",   # blue    — CSS property:
        "key":       "#82aaff",   # blue    — JSON \"key\":
        "heading":   "#ffcb6b",   # amber   — Markdown # heading
        "bold":      "#c792ea",   # purple  — Markdown **bold**
        "inlinecode":"#c3e88d",   # lime    — Markdown `code`
    }

    # ── Language pattern tables (tag, pattern [, extra_re_flags]) ────────
    # Patterns are applied in ORDER — later patterns win over earlier ones.
    # If a pattern contains group 1, only group 1 is coloured.
    _LANG: dict = {
        "python": [
            ("string",   r'"""[\s\S]*?"""|\'\'\' [\s\S]*?\'\'\'', re.DOTALL),
            ("string",   r'"(?:\\.|[^"\\])*"|\' (?:\\.|[^\'\\])*\''),
            ("comment",  r"#[^\n]*"),
            ("decorator",r"@[\w.]+"),
            ("keyword",  r"\b(?:False|None|True|and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)\b"),
            ("builtin",  r"\b(?:abs|all|any|bin|bool|bytes|callable|chr|classmethod|complex|dict|dir|divmod|enumerate|eval|exec|filter|float|format|frozenset|getattr|globals|hasattr|hash|hex|id|input|int|isinstance|issubclass|iter|len|list|locals|map|max|min|next|object|oct|open|ord|pow|print|property|range|repr|reversed|round|set|setattr|slice|sorted|staticmethod|str|sum|super|tuple|type|vars|zip)\b"),
            ("class_",   r"\bclass\s+([A-Za-z_]\w*)"),
            ("function", r"\bdef\s+([A-Za-z_]\w*)"),
            ("function", r"\b([A-Za-z_]\w*)\s*(?=\()"),
            ("constant", r"\b[A-Z_][A-Z_\d]{2,}\b"),
            ("number",   r"\b(?:0x[\da-fA-F]+|0o[0-7]+|0b[01]+|\d+\.?\d*(?:[eE][+-]?\d+)?)\b"),
            ("operator", r"[+\-*/%&|^~<>=!]+|\.\.\.|\.\."),
        ],
        "js": [
            ("string",   r"`[\s\S]*?`", re.DOTALL),
            ("string",   r'"(?:\\.|[^"\\])*"|\' (?:\\.|[^\'\\])*\''),
            ("comment",  r"//[^\n]*"),
            ("comment",  r"/\*[\s\S]*?\*/", re.DOTALL),
            ("keyword",  r"\b(?:break|case|catch|class|const|continue|debugger|default|delete|do|else|export|extends|finally|for|function|if|import|in|instanceof|let|new|of|return|static|super|switch|this|throw|try|typeof|var|void|while|with|yield|async|await)\b"),
            ("keyword2", r"\b(?:true|false|null|undefined|NaN|Infinity)\b"),
            ("class_",   r"\bclass\s+([A-Za-z_]\w*)"),
            ("function", r"\bfunction\s+([A-Za-z_]\w*)"),
            ("function", r"\b([A-Za-z_]\w*)\s*(?=\()"),
            ("constant", r"\b[A-Z_][A-Z_\d]{2,}\b"),
            ("number",   r"\b(?:0x[\da-fA-F]+|\d+\.?\d*(?:[eE][+-]?\d+)?)\b"),
            ("operator", r"[+\-*/%&|^~<>=!?:]+|\.\.\.|\.\?\."),
        ],
        "cpp": [
            ("comment",  r"//[^\n]*"),
            ("comment",  r"/\*[\s\S]*?\*/", re.DOTALL),
            ("string",   r'"(?:\\.|[^"\\])*"|\' (?:\\.|[^\'\\])*\''),
            ("decorator",r"#\s*(?:include|define|ifdef|ifndef|endif|pragma|undef|if|else|elif)[^\n]*"),
            ("decorator",r"\[[^\]]*\]"),   # C# [Attribute]
            ("keyword",  r"\b(?:auto|break|case|catch|char|class|const|constexpr|continue|default|delete|do|double|else|enum|explicit|extern|false|float|for|friend|goto|if|inline|int|long|namespace|new|nullptr|operator|private|protected|public|return|short|signed|sizeof|static|struct|switch|template|this|throw|true|try|typedef|typename|union|unsigned|using|virtual|void|volatile|while)\b"),
            ("keyword2", r"\b(?:abstract|var|string|bool|byte|decimal|delegate|dynamic|event|interface|internal|object|out|override|params|readonly|ref|sealed|typeof|var|async|await)\b"),
            ("class_",   r"\b(?:class|struct|enum|interface)\s+([A-Za-z_]\w*)"),
            ("function", r"\b([A-Za-z_]\w*)\s*(?=\()"),
            ("constant", r"\b[A-Z_][A-Z_\d]{2,}\b"),
            ("number",   r"\b(?:0x[\da-fA-F]+|\d+\.?\d*[fFdDuUlL]*)\b"),
            ("operator", r"[+\-*/%&|^~<>=!:?]+|::|->|=>"),
        ],
        "go": [
            ("string",   r'`[\s\S]*?`', re.DOTALL),
            ("string",   r'"(?:\\.|[^"\\])*"|\' (?:\\.|[^\'\\])*\''),
            ("comment",  r"//[^\n]*"),
            ("comment",  r"/\*[\s\S]*?\*/", re.DOTALL),
            ("keyword",  r"\b(?:break|case|chan|const|continue|default|defer|else|fallthrough|for|func|go|goto|if|import|interface|map|package|range|return|select|struct|switch|type|var)\b"),
            ("keyword2", r"\b(?:true|false|nil|iota)\b"),
            ("builtin",  r"\b(?:append|cap|close|complex|copy|delete|imag|len|make|new|panic|print|println|real|recover)\b"),
            ("class_",   r"\btype\s+([A-Za-z_]\w*)"),
            ("function", r"\bfunc\s+(?:\([^)]*\)\s+)?([A-Za-z_]\w*)"),
            ("function", r"\b([A-Za-z_]\w*)\s*(?=\()"),
            ("number",   r"\b(?:0x[\da-fA-F]+|\d+\.?\d*(?:[eE][+-]?\d+)?)\b"),
            ("operator", r"[+\-*/%&|^~<>=!:]+|\.\.\."),
        ],
        "rs": [
            ("string",   r'"(?:\\.|[^"\\])*"'),
            ("comment",  r"//[^\n]*"),
            ("comment",  r"/\*[\s\S]*?\*/", re.DOTALL),
            ("decorator",r"#\[?[\s\S]*?\]"),
            ("keyword",  r"\b(?:as|async|await|break|const|continue|crate|dyn|else|enum|extern|fn|for|if|impl|in|let|loop|match|mod|move|mut|pub|ref|return|self|Self|static|struct|super|trait|type|unsafe|use|where|while)\b"),
            ("keyword2", r"\b(?:true|false|None|Some|Ok|Err)\b"),
            ("class_",   r"\b(?:struct|enum|trait|impl)\s+([A-Za-z_]\w*)"),
            ("function", r"\bfn\s+([A-Za-z_]\w*)"),
            ("function", r"\b([A-Za-z_]\w*)\s*(?=\()"),
            ("constant", r"\b[A-Z_][A-Z_\d]{2,}\b"),
            ("number",   r"\b(?:0x[\da-fA-F]+|0o[0-7]+|0b[01]+|\d+\.?\d*(?:[eE][+-]?\d+)?)\b"),
            ("operator", r"[+\-*/%&|^~<>=!:?]+|->|=>|\.\.\.|\.\.\.\."),
        ],
        "java": [
            ("comment",  r"//[^\n]*"),
            ("comment",  r"/\*[\s\S]*?\*/", re.DOTALL),
            ("string",   r'"(?:\\.|[^"\\])*"|\' (?:\\.|[^\'\\])*\''),
            ("decorator",r"@[A-Za-z_]\w*"),
            ("keyword",  r"\b(?:abstract|assert|break|case|catch|class|const|continue|default|do|else|enum|extends|final|finally|for|goto|if|implements|import|instanceof|interface|native|new|package|private|protected|public|return|static|strictfp|super|switch|synchronized|this|throw|throws|transient|try|var|void|volatile|while)\b"),
            ("keyword2", r"\b(?:true|false|null)\b"),
            ("builtin",  r"\b(?:boolean|byte|char|double|float|int|long|short|String|Object|System|Math|Arrays|List|Map|Set|ArrayList|HashMap)\b"),
            ("class_",   r"\b(?:class|interface|enum)\s+([A-Za-z_]\w*)"),
            ("function", r"\b([A-Za-z_]\w*)\s*(?=\()"),
            ("number",   r"\b(?:0x[\da-fA-F]+|\d+\.?\d*[fFdDlL]?)\b"),
            ("operator", r"[+\-*/%&|^~<>=!:?]+|::"),
        ],
        "html": [
            ("comment",  r"<!--[\s\S]*?-->", re.DOTALL),
            ("string",   r'"[^"]*"|\' [^\']*\''),
            ("tag",      r"</?\.?([A-Za-z][\w.-]*)"),
            ("attr",     r"\b([A-Za-z_][\w:.-]*)\s*(?==)"),
        ],
        "css": [
            ("comment",  r"/\*[\s\S]*?\*/", re.DOTALL),
            ("string",   r'"[^"]*"|\' [^\']*\''),
            ("selector", r"[.#][\w-]+|::{1,2}[\w-]+|:\w[\w-]*(?!\s*[^{,])|\.\w+"),
            ("property", r"  [\w-]+(?=\s*:)"),
            ("keyword",  r"\b(?:auto|none|inherit|initial|unset|flex|grid|block|inline|absolute|relative|fixed|sticky|center|left|right|top|bottom|solid|dotted|dashed|transparent|important)\b"),
            ("number",   r"\b\d+(?:\.\d+)?(?:px|em|rem|%|vh|vw|deg|s|ms|fr)?\b"),
        ],
        "json": [
            ("key",      r'"([^"\\]|\\.)*?"(?=\s*:)'),
            ("string",   r'"(?:[^"\\]|\\.)*"'),
            ("number",   r"\b-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b"),
            ("keyword2", r"\b(?:true|false|null)\b"),
        ],
        "bash": [
            ("comment",  r"#[^\n]*"),
            ("string",   r'"(?:\\.|[^"\\])*"|\' [^\']*\''),
            ("keyword",  r"\b(?:if|then|else|elif|fi|for|do|done|while|until|case|esac|function|return|exit|break|continue|local|export|source|readonly|declare|unset|shift|trap)\b"),
            ("builtin",  r"\b(?:echo|printf|read|cd|ls|pwd|mkdir|rm|cp|mv|cat|grep|sed|awk|find|curl|wget|chmod|chown|sudo|apt|pip|python|python3|node|npm|git|docker)\b"),
            ("decorator",r"\$\{?[A-Za-z_]\w*\}?"),   # $VAR
            ("number",   r"\b\d+\b"),
            ("operator",  r"[|&;<>!]+|&&|\|\|"),
        ],
        "markdown": [
            ("heading",    r"^#{1,6}\s+.+$"),
            ("bold",       r"\*\*[\s\S]*?\*\*|__[\s\S]*?__"),
            ("comment",    r"<!--[\s\S]*?-->", re.DOTALL),
            ("inlinecode", r"`[^`]+`"),
            ("string",     r"```[\s\S]*?```", re.DOTALL),
            ("decorator",  r"^\s*[-*+]\s"),
            ("number",     r"^\s*\d+\.\s"),
            ("function",   r"\[[^\]]+\]\([^)]+\)"),   # [link](url)
        ],
    }
    # Aliases
    _ALIASES = {
        "jsx": "js", "tsx": "js", "ts": "js",
        "c": "cpp", "h": "cpp", "hpp": "cpp", "cc": "cpp", "cxx": "cpp", "cs": "cpp",
        "sh": "bash", "bat": "bash", "zsh": "bash", "fish": "bash",
        "yml": "json",  # close enough for structure
        "toml": "json",
        "vue": "html",
    }
    # Tags with font styling
    _FONT_TAGS = {
        "comment":   ("JetBrains Mono", 11, "italic"),
        "keyword":   ("JetBrains Mono", 11, "bold"),
        "class_":    ("JetBrains Mono", 11, "bold"),
        "heading":   ("JetBrains Mono", 12, "bold"),
        "bold":      ("JetBrains Mono", 11, "bold"),
    }

    def __init__(self, text_widget: tk.Text):
        self.text = text_widget
        self._hl_after_id = None
        self._configure_tags()

    def _configure_tags(self):
        t = self.text
        for tag, color in self._C.items():
            font = self._FONT_TAGS.get(tag, ("JetBrains Mono", 11))
            t.tag_configure(tag, foreground=color, font=font)
        # Ensure hl tags are below selection highlight
        for tag in self._C:
            t.tag_lower(tag, "sel")

    def apply(self, lang: str):
        """Apply highlighting for the given file extension. Clears previous highlights."""
        lang = lang.lower().lstrip(".")
        lang = self._ALIASES.get(lang, lang)
        patterns = self._LANG.get(lang, [])
        if not patterns:
            return

        content = self.text.get("1.0", "end-1c")
        if len(content) > 150_000:          # skip huge files for performance
            return

        # Clear all previous tag ranges
        for tag in self._C:
            self.text.tag_remove(tag, "1.0", "end")

        for entry in patterns:
            tag, pattern = entry[0], entry[1]
            extra_flags  = entry[2] if len(entry) > 2 else 0
            flags        = re.MULTILINE | extra_flags
            try:
                for m in re.finditer(pattern, content, flags):
                    # Use group 1 if available (e.g. capture just the name)
                    if m.lastindex and m.lastindex >= 1:
                        s, e = m.start(1), m.end(1)
                    else:
                        s, e = m.start(), m.end()
                    self.text.tag_add(tag,
                                      self._idx(content, s),
                                      self._idx(content, e))
            except re.error:
                pass

    def schedule(self, lang: str, delay_ms: int = 300):
        """Debounced highlight — cancels any pending call and reschedules."""
        if self._hl_after_id:
            self.text.after_cancel(self._hl_after_id)
        self._hl_after_id = self.text.after(delay_ms, lambda: self.apply(lang))

    @staticmethod
    def _idx(content: str, char_pos: int) -> str:
        """Convert char offset → Tkinter 'line.col' index."""
        before = content[:char_pos]
        line   = before.count("\n") + 1
        col    = char_pos - (before.rfind("\n") + 1)
        return f"{line}.{col}"


class CodeViewer(ctk.CTkFrame):
    """Tabbed code viewer with line numbers, syntax highlighting, Save, AI Review and Revamp."""

    def __init__(self, master, on_review, on_revamp, **kw):
        super().__init__(master, fg_color=BG, corner_radius=0, **kw)
        self.on_review = on_review
        self.on_revamp = on_revamp
        self._tabs: dict[str, dict] = {}
        self._active: str | None = None
        self._build()
        # Highlighter is wired in _build after the text widget exists

    def _build(self):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Tab bar
        self._tab_bar = ctk.CTkFrame(self, fg_color=S2, corner_radius=0, height=36)
        self._tab_bar.grid(row=0, column=0, sticky="ew")
        self._tab_bar_inner = ctk.CTkFrame(self._tab_bar, fg_color="transparent")
        self._tab_bar_inner.pack(side="left", fill="y")

        # Empty placeholder
        self._empty = ctk.CTkLabel(
            self, text="📝  Open a file from the Explorer",
            font=("Inter", 14), text_color=DIM)
        self._empty.grid(row=1, column=0)

        # Editor area (hidden until a file opens)
        self._editor_frame = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        self._editor_frame.grid(row=1, column=0, sticky="nsew")
        self._editor_frame.grid_rowconfigure(0, weight=1)
        self._editor_frame.grid_columnconfigure(1, weight=1)
        self._editor_frame.grid_remove()   # hidden initially

        # Line numbers (narrow textbox on left)
        self._ln_box = tk.Text(
            self._editor_frame,
            width=4, state="disabled",
            bg=S2, fg=MUTED, bd=0,
            font=("JetBrains Mono", 11),
            padx=8, pady=6,
            selectbackground=S2, relief="flat",
            cursor="arrow",
        )
        self._ln_box.grid(row=0, column=0, sticky="nsew")

        # Main editor (editable)
        self._code_box = tk.Text(
            self._editor_frame,
            state="normal",
            bg=BG, fg=TEXT, bd=0,
            insertbackground=ACCENT,
            font=("JetBrains Mono", 11),
            padx=12, pady=6,
            selectbackground="#3a2060",
            relief="flat", wrap="none",
            undo=True,
        )
        self._code_box.grid(row=0, column=1, sticky="nsew")
        # Sync scroll
        vsb = tk.Scrollbar(self._editor_frame, command=self._scroll_both,
                           bg=S3, troughcolor=S2)
        vsb.grid(row=0, column=2, sticky="ns")
        hsb = tk.Scrollbar(self._editor_frame, orient="horizontal",
                           command=self._code_box.xview,
                           bg=S3, troughcolor=S2)
        hsb.grid(row=1, column=1, sticky="ew")
        self._code_box.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._code_box.bind("<<Modified>>", self._on_edit)

        # Syntax highlighter — initialise now that the Text widget exists
        self._highlighter = SyntaxHighlighter(self._code_box)

        # Action bar
        action = ctk.CTkFrame(self, fg_color=S2, corner_radius=0, height=44)
        action.grid(row=2, column=0, sticky="ew")
        action.grid_propagate(False)
        action.grid_columnconfigure(6, weight=1)

        self._path_lbl = ctk.CTkLabel(action, text="", font=("JetBrains Mono", 10),
                                      text_color=MUTED, anchor="w")
        self._path_lbl.grid(row=0, column=0, padx=12, pady=0, sticky="w")

        self._save_btn = ctk.CTkButton(
            action, text="💾 Save", width=72, height=28,
            font=F_SMALL, fg_color=S3, hover_color=BORDER,
            text_color=GREEN, corner_radius=6,
            command=self._save_file)
        self._save_btn.grid(row=0, column=1, padx=4, pady=8)

        ctk.CTkButton(
            action, text="🔍 Review", width=80, height=28,
            font=F_SMALL, fg_color=S3, hover_color=BORDER,
            text_color=CYAN, corner_radius=6,
            command=self._do_review).grid(row=0, column=2, padx=4, pady=8)

        ctk.CTkButton(
            action, text="✨ Revamp", width=80, height=28,
            font=F_SMALL, fg_color=S3, hover_color=BORDER,
            text_color=ACCENT, corner_radius=6,
            command=self._do_revamp).grid(row=0, column=3, padx=4, pady=8)

        ctk.CTkButton(
            action, text="📋 Copy Path", width=90, height=28,
            font=F_SMALL, fg_color=S3, hover_color=BORDER,
            text_color=MUTED, corner_radius=6,
            command=self._copy_path).grid(row=0, column=4, padx=4, pady=8)

        self._modified_lbl = ctk.CTkLabel(action, text="", font=F_SMALL,
                                          text_color=YELLOW)
        self._modified_lbl.grid(row=0, column=5, padx=8)

    # ── Scroll helpers
    def _scroll_both(self, *args):
        self._code_box.yview(*args)
        self._ln_box.yview(*args)

    def _update_line_numbers(self):
        content = self._code_box.get("1.0", "end-1c")
        n = content.count("\n") + 1
        nums = "\n".join(str(i) for i in range(1, n + 1))
        self._ln_box.configure(state="normal")
        self._ln_box.delete("1.0", "end")
        self._ln_box.insert("1.0", nums)
        self._ln_box.configure(state="disabled")

    def _on_edit(self, _event=None):
        if self._active and self._code_box.edit_modified():
            self._tabs[self._active]["modified"] = True
            self._modified_lbl.configure(text="● unsaved")
            self._code_box.edit_modified(False)
            self._update_line_numbers()
            # Debounced highlight — 300 ms after last keystroke
            if self._active:
                lang = self._tabs[self._active]["path"].suffix
                self._highlighter.schedule(lang, delay_ms=300)

    # ── Open file
    def open_file(self, path: Path):
        key = str(path)
        if key not in self._tabs:
            self._tabs[key] = {"path": path, "modified": False}
            self._add_tab_btn(key, path.name)
        self._switch_tab(key)

    def reload_file(self, path: Path):
        """Re-read file from disk if it is currently open (called after AI writes it)."""
        key = str(path)
        if key == self._active:
            self._load_content(path)

    def _load_content(self, path: Path):
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            content = f"[error reading file]\n{exc}"
        self._code_box.configure(state="normal")
        self._code_box.delete("1.0", "end")
        self._code_box.insert("1.0", content)
        self._code_box.edit_modified(False)
        if self._active:
            self._tabs[self._active]["modified"] = False
        self._modified_lbl.configure(text="")
        self._update_line_numbers()
        # Apply syntax highlighting immediately
        self._highlighter.apply(path.suffix)

    # ── Tab management
    def _add_tab_btn(self, key: str, name: str):
        frm = ctk.CTkFrame(self._tab_bar_inner, fg_color="transparent")
        frm.pack(side="left", padx=(2, 0), pady=4)

        btn = ctk.CTkButton(
            frm, text=name, font=F_SMALL,
            height=28, fg_color=S3, hover_color=BORDER,
            text_color=TEXT, corner_radius=6,
            command=lambda k=key: self._switch_tab(k))
        btn.pack(side="left")

        close = ctk.CTkButton(
            frm, text="✕", width=20, height=28,
            font=("Inter", 10), fg_color=S3, hover_color="#3a1010",
            text_color=MUTED, corner_radius=6,
            command=lambda k=key, f=frm: self._close_tab(k, f))
        close.pack(side="left", padx=(0, 2))

        self._tabs[key]["tab_frame"] = frm

    def _switch_tab(self, key: str):
        self._active = key
        tab = self._tabs[key]
        path = tab["path"]
        self._path_lbl.configure(text=str(path))
        self._load_content(path)
        self._empty.grid_remove()
        self._editor_frame.grid()
        # Highlight active tab
        for k, t in self._tabs.items():
            frm = t.get("tab_frame")
            if frm:
                for child in frm.winfo_children():
                    child.configure(fg_color=S2 if k == key else S3)

    def _close_tab(self, key: str, tab_frame):
        if self._tabs[key].get("modified"):
            if not messagebox.askyesno(
                    "Unsaved changes",
                    f"{self._tabs[key]['path'].name} has unsaved changes. Close anyway?",
                    parent=self):
                return
        tab_frame.destroy()
        del self._tabs[key]
        if self._active == key:
            self._active = None
            self._editor_frame.grid_remove()
            self._empty.grid()
            if self._tabs:
                self._switch_tab(next(iter(self._tabs)))

    # ── Context API (used by ClawApp for Antigravity-style awareness)
    def get_context(self) -> dict | None:
        """Return open file path + full content for AI context injection."""
        if not self._active:
            return None
        path = self._tabs[self._active]["path"]
        content = self._code_box.get("1.0", "end-1c")
        return {"path": path, "content": content}

    def get_selection(self) -> str | None:
        """Return currently selected text in the code editor, or None."""
        try:
            sel = self._code_box.get(tk.SEL_FIRST, tk.SEL_LAST)
            return sel if sel.strip() else None
        except tk.TclError:
            return None

    # ── Action bar callbacks
    def _save_file(self):
        if not self._active:
            return
        path = self._tabs[self._active]["path"]
        content = self._code_box.get("1.0", "end-1c")
        try:
            path.write_text(content, encoding="utf-8")
            self._tabs[self._active]["modified"] = False
            self._modified_lbl.configure(text="✔ saved", text_color=GREEN)
            self.after(2000, lambda: self._modified_lbl.configure(text=""))
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc), parent=self)

    def _do_review(self):
        if not self._active:
            return
        path = self._tabs[self._active]["path"]
        content = self._code_box.get("1.0", "end-1c")
        self.on_review(path, content)

    def _do_revamp(self):
        if not self._active:
            return
        path = self._tabs[self._active]["path"]
        content = self._code_box.get("1.0", "end-1c")
        self.on_revamp(path, content)

    def _copy_path(self):
        if not self._active:
            return
        self.clipboard_clear()
        self.clipboard_append(str(self._tabs[self._active]["path"]))


# ══════════════════════════════════════════════════════════════════════════════
#  TextMeasurer  —  pretext concept ported to Python/Tkinter
#  prepare()  : one-time pass — segments text & caches each word's pixel width
#               using Tkinter's own font engine (same ground-truth as rendering)
#  layout()   : pure arithmetic — counts visual lines at any max_width,
#               returns exact pixel height. Zero DOM/widget touches.
# ══════════════════════════════════════════════════════════════════════════════
class TextMeasurer:
    """Port of the pretext text-measurement technique for Tkinter."""

    _font_cache: dict = {}   # (family, size) -> tkfont.Font

    @classmethod
    def _get_font(cls, family: str, size: int) -> tkfont.Font:
        key = (family, size)
        if key not in cls._font_cache:
            cls._font_cache[key] = tkfont.Font(family=family, size=size)
        return cls._font_cache[key]

    @classmethod
    def prepare(cls, text: str, family: str = "Inter", size: int = 13) -> dict:
        """
        One-time measurement pass (analogous to pretext's prepare()).
        Splits text on hard newlines, then on spaces, and measures every
        word's pixel width once.  Returns an opaque dict for layout().
        """
        fnt        = cls._get_font(family, size)
        space_w    = fnt.measure(" ")
        line_h     = fnt.metrics("linespace")
        hard_lines = text.split("\n")

        lines_data = []
        for hard_line in hard_lines:
            words = hard_line.split(" ") if hard_line else []
            lines_data.append(
                [(w, fnt.measure(w)) for w in words]
            )

        return {"lines": lines_data, "space_w": space_w, "line_h": line_h}

    @classmethod
    def layout(cls, prepared: dict, max_width: int,
               pad_v: int = 20) -> int:
        """
        Pure-arithmetic layout pass (analogous to pretext's layout()).
        Counts visual lines by walking cached word widths — no widgets,
        no reflow.  Returns the exact pixel height for a bubble.
        """
        sw       = prepared["space_w"]
        lh       = prepared["line_h"]
        max_width = max(max_width, 40)   # guard against tiny widths

        visual_lines = 0
        for words in prepared["lines"]:
            visual_lines += 1            # every hard line = at least 1 visual row
            cur_x = 0
            for i, (_w, px) in enumerate(words):
                if i == 0:
                    cur_x = px
                else:
                    if cur_x + sw + px > max_width:
                        visual_lines += 1
                        cur_x = px
                    else:
                        cur_x += sw + px

        if visual_lines == 0:
            visual_lines = 1

        return visual_lines * lh + pad_v


# ══════════════════════════════════════════════════════════════════════════════
#  Chat Area
# ══════════════════════════════════════════════════════════════════════════════
class ChatArea(ctk.CTkScrollableFrame):
    # Horizontal padding subtracted from chat width to get text render width
    _BUBBLE_H_PAD = 60    # 20px outer padx each side + ~20px inner textbox pad
    _TEXT_PAD_V   = 24    # top+bottom textbox internal padding (px)
    _TEXT_PAD_H   = 28    # left+right textbox internal padding (px)

    def __init__(self, master, **kw):
        super().__init__(master, fg_color=BG, corner_radius=0, **kw)
        self.grid_columnconfigure(0, weight=1)
        self._row = 0
        self._thinking_widget = None
        self._thinking_lbl    = None
        self._streaming_box   = None   # CTkTextbox for streaming
        self._streaming_prep  = None   # prepared text for streaming bubble
        self._streaming_text  = ""
        self._anim_step       = 0
        # Registry: list of (CTkTextbox, prepared_dict) for live height updates
        self._bubble_registry: list[tuple] = []
        self._show_welcome()
        self.bind("<Configure>", self._on_resize)

    # ── Resize handler — recompute every bubble height+width (pure arithmetic) ───
    def _on_resize(self, event=None):
        chat_w = self.winfo_width()
        if chat_w < 100:
            return
        text_w = self._calc_text_width(chat_w)
        box_w  = text_w + self._TEXT_PAD_H
        for box, prep in self._bubble_registry:
            try:
                if box.winfo_exists():
                    h = TextMeasurer.layout(prep, text_w, pad_v=self._TEXT_PAD_V)
                    box.configure(height=h, width=box_w)
            except Exception:
                pass

    def _calc_text_width(self, chat_w: int | None = None) -> int:
        """Text render width inside a bubble given the current chat area width."""
        if chat_w is None:
            chat_w = self.winfo_width()
        if chat_w < 100:
            chat_w = 900   # safe fallback before first layout pass
        return max(80, chat_w - self._BUBBLE_H_PAD - self._TEXT_PAD_H)

    def _bubble_text_width(self) -> int:
        return self._calc_text_width()

    def _make_bubble_box(self, parent, text: str,
                         fg: str, text_color: str) -> ctk.CTkTextbox:
        """
        Create a CTkTextbox whose height AND width are pixel-perfect via
        TextMeasurer.  Width is set explicitly so the rendered box always
        matches the width assumption used for height calculation.
        """
        prep   = TextMeasurer.prepare(text, family="Inter", size=13)
        text_w = self._bubble_text_width()
        h      = TextMeasurer.layout(prep, text_w, pad_v=self._TEXT_PAD_V)
        box_w  = text_w + self._TEXT_PAD_H

        box = ctk.CTkTextbox(
            parent, height=h, width=box_w,
            font=F_BODY, text_color=text_color,
            fg_color=fg, border_width=0,
            corner_radius=12, wrap="word",
            activate_scrollbars=False,
        )
        box.insert("1.0", text)
        box.configure(state="disabled")
        self._bubble_registry.append((box, prep))
        return box

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
        box = self._make_bubble_box(wrap, text,
                                    fg="#1a1030", text_color=TEXT)
        box.grid(row=1, column=0, sticky="e")
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
        # Start with correct width + single-line height; grows token by token
        text_w = self._bubble_text_width()
        self._streaming_box = ctk.CTkTextbox(
            wrap, height=40, width=text_w + self._TEXT_PAD_H,
            font=F_BODY, text_color=TEXT,
            fg_color=S2, border_width=0,
            corner_radius=12, wrap="word",
            activate_scrollbars=False,
        )
        self._streaming_box.grid(row=1, column=0, sticky="ew")
        self._streaming_prep  = None
        self._streaming_text  = ""

    def append_token(self, tok):
        self._streaming_text += tok
        if self._streaming_box and self._streaming_box.winfo_exists():
            box = self._streaming_box
            box.configure(state="normal")
            box.delete("1.0", "end")
            box.insert("1.0", self._streaming_text)
            box.configure(state="disabled")
            # Recompute height+width on every token using TextMeasurer
            prep   = TextMeasurer.prepare(self._streaming_text, "Inter", 13)
            text_w = self._bubble_text_width()
            h      = TextMeasurer.layout(prep, text_w, pad_v=self._TEXT_PAD_V)
            box.configure(height=h, width=text_w + self._TEXT_PAD_H)
        self._scroll_bottom()

    def finalize_streaming(self, full_text):
        if self._streaming_box and self._streaming_box.winfo_exists():
            box  = self._streaming_box
            box.configure(state="normal")
            box.delete("1.0", "end")
            box.insert("1.0", full_text)
            box.configure(state="disabled")
            # Final precise height+width + register for future resizes
            prep   = TextMeasurer.prepare(full_text, "Inter", 13)
            text_w = self._bubble_text_width()
            h      = TextMeasurer.layout(prep, text_w, pad_v=self._TEXT_PAD_V)
            box.configure(height=h, width=text_w + self._TEXT_PAD_H)
            self._bubble_registry.append((box, prep))
        self._streaming_box  = None
        self._streaming_prep = None
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
        box = self._make_bubble_box(wrap, text, fg=S2, text_color=TEXT)
        box.grid(row=1, column=0, sticky="ew")
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
        full = f"❌  {msg}"
        wrap = ctk.CTkFrame(self, fg_color="transparent")
        wrap.grid(row=self._next(), column=0, sticky="ew", padx=20, pady=(0, 8))
        wrap.grid_columnconfigure(0, weight=1)
        box = self._make_bubble_box(wrap, full, fg="#1a0808", text_color=RED)
        box.grid(row=0, column=0, sticky="ew")
        self._scroll_bottom()

    def clear(self):
        for w in self.winfo_children():
            w.destroy()
        self._row            = 0
        self._thinking_widget = None
        self._thinking_lbl    = None
        self._streaming_box   = None
        self._streaming_prep  = None
        self._streaming_text  = ""
        self._bubble_registry = []
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
        self.title("Claw Agent  —  IDE Mode")
        self.geometry("1600x900")
        self.minsize(1100, 680)
        self.configure(fg_color=BG)

        self.agent       = None
        self.event_queue = queue.Queue()
        self.busy        = False
        self._cur_pill   = None

        # Set default working directory to Desktop
        _desktop = Path.home() / "Desktop"
        if _desktop.exists():
            os.chdir(_desktop)
            self._cwd = _desktop
        else:
            self._cwd = Path.cwd()

        self._build_layout()
        self._load_models()
        self.after(80, self._poll_events)

    # ── Build layout ─────────────────────────────────────────────────────────
    def _build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Sidebar (fixed left column)
        self.sidebar = Sidebar(
            self,
            on_model_change=self._on_model_change,
            on_clear=self._clear_chat,
            on_save=self._save_session,
            on_refresh=self._refresh_models,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        # ── Resizable PanedWindow: Explorer | CodeViewer | Chat
        self._paned = tk.PanedWindow(
            self, orient=tk.HORIZONTAL,
            bg=BORDER, sashwidth=5, sashpad=0,
            relief="flat", bd=0,
        )
        self._paned.grid(row=0, column=1, sticky="nsew")

        # Pane 1: File Explorer
        self.explorer = FileExplorer(
            self._paned,
            on_open_file=self._open_file,
            on_cwd_change=self._on_cwd_change,
        )
        self._paned.add(self.explorer, minsize=160, width=220)

        # Pane 2: Code Viewer
        self.code_viewer = CodeViewer(
            self._paned,
            on_review=self._review_file,
            on_revamp=self._revamp_file,
        )
        self._paned.add(self.code_viewer, minsize=240, width=560)

        # Pane 3: Chat
        chat_pane = ctk.CTkFrame(self._paned, fg_color=BG, corner_radius=0)
        self._paned.add(chat_pane, minsize=300)
        chat_pane.grid_rowconfigure(1, weight=1)
        chat_pane.grid_columnconfigure(0, weight=1)

        # Header bar
        hdr = ctk.CTkFrame(chat_pane, fg_color=SURF, height=50, corner_radius=0)
        hdr.grid(row=0, column=0, sticky="ew")
        hdr.grid_columnconfigure(0, weight=1)
        hdr.grid_propagate(False)
        ctk.CTkLabel(hdr, text="🦞 Claw Agent — IDE", font=F_TITLE,
                     text_color=TEXT).grid(row=0, column=0, padx=20, pady=13, sticky="w")
        self.status_lbl = ctk.CTkLabel(hdr, text="● Idle", font=F_SMALL,
                                       text_color=GREEN)
        self.status_lbl.grid(row=0, column=1, padx=20, pady=13, sticky="e")

        # Chat area
        self.chat = ChatArea(chat_pane)
        self.chat.grid(row=1, column=0, sticky="nsew")

        # Input area
        self.inp_frame = ctk.CTkFrame(chat_pane, fg_color=SURF, corner_radius=0)
        self.inp_frame.grid(row=2, column=0, sticky="ew")
        self.inp_frame.grid_columnconfigure(0, weight=1)

        # Context hint bar (shows currently open file if any)
        self._ctx_bar = ctk.CTkFrame(self.inp_frame, fg_color="transparent")
        self._ctx_bar.grid(row=0, column=0, padx=16, pady=(10, 0), sticky="ew")
        self._ctx_bar.grid_columnconfigure(1, weight=1)
        self._ctx_file_lbl = ctk.CTkLabel(
            self._ctx_bar, text="", font=("JetBrains Mono", 9),
            text_color=ACCENT, anchor="w")
        self._ctx_file_lbl.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            self._ctx_bar, text="@ Add context", width=96, height=22,
            font=("Inter", 9), fg_color=S3, hover_color=BORDER,
            text_color=MUTED, corner_radius=5,
            command=self._inject_context,
        ).grid(row=0, column=1, sticky="e")

        box = ctk.CTkFrame(self.inp_frame, fg_color=S2, corner_radius=14)
        box.grid(row=1, column=0, padx=16, pady=(6, 6), sticky="ew", columnspan=2)
        box.grid_columnconfigure(0, weight=1)

        self.input_box = ctk.CTkTextbox(
            box, height=48, font=F_BODY, text_color=TEXT,
            fg_color="transparent", border_width=0, wrap="word",
        )
        self.input_box.grid(row=0, column=0, padx=(14, 6), pady=6, sticky="ew")
        self.input_box.bind("<Return>", self._on_enter)
        self.input_box.bind("<Shift-Return>", lambda e: None)
        self.input_box.bind("<KeyRelease>", self._auto_grow_input)

        self.send_btn = ctk.CTkButton(
            box, text="➤", width=46, height=46, font=("Inter", 16, "bold"),
            fg_color=ACCENT, hover_color="#8058ee", text_color="white",
            corner_radius=11, command=self._send,
        )
        self.send_btn.grid(row=0, column=1, padx=(0, 8), pady=6)

        ctk.CTkLabel(self.inp_frame,
                     text="Enter to send · Shift+Enter for newline · Ctrl+L focus chat",
                     font=("Inter", 9), text_color=DIM
                     ).grid(row=2, column=0, padx=20, pady=(0, 6), sticky="e", columnspan=2)

        # Keyboard shortcuts
        self.bind_all("<Control-l>", lambda e: self.input_box.focus_set())
        self.bind_all("<Control-L>", lambda e: self.input_box.focus_set())

    # ── Model loading ─────────────────────────────────────────────────────────
    def _load_models(self):
        """Initial model load on startup."""
        self._refresh_models(keep_selection=False)
        self._schedule_model_auto_refresh()

    def _refresh_models(self, keep_selection=True, done_cb=None):
        """Re-query Ollama live. Safe to call anytime — runs in a background thread."""
        def fetch():
            models = []
            if OLLAMA_OK and OllamaBackend.is_running():
                models += OllamaBackend.list_models()
            has_key = bool(os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
            if GEMINI_OK and has_key:
                models.append("gemini")
            self.after(0, lambda m=models, ks=keep_selection: self.sidebar.set_models(m, keep_selection=ks))
            if done_cb:
                self.after(0, done_cb)
        threading.Thread(target=fetch, daemon=True).start()

    def _schedule_model_auto_refresh(self):
        """Auto-refresh every 30 s so newly pulled models appear automatically."""
        def auto_refresh():
            self._refresh_models(keep_selection=True)      # silent, keeps current model
            self.after(30_000, auto_refresh)               # schedule next tick
        self.after(30_000, auto_refresh)

    def _on_model_change(self, model):
        if self.agent:
            # Preserve conversation history across model switches
            self._old_messages = list(self.agent.messages)
            self._old_turns = self.agent.turn_count
        self.agent = None   # force recreate on next send
        # Immediately reflect the new model name in the STATUS panel
        self.sidebar.s_model.configure(text=model.split("/")[-1][:22])
        self.sidebar.update_status(busy=self.busy)

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
        self.input_box.configure(height=48)
        model = self.sidebar.model_var.get()

        # Chat bubble shows the user's raw text, AI gets context-enriched version
        self.chat.append_user(text)
        self._set_busy(True)
        ai_text = self._build_send_text(text)

        def run():
            try:
                self._ensure_agent(model)
                self.agent.run_turn_streaming(ai_text, self.event_queue)
            except Exception as exc:
                self.event_queue.put({"type": "error", "message": str(exc)})
            finally:
                self.event_queue.put(None)

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
                    # Remember if agent is writing a file
                    if ev["name"] in ("write_file", "edit_file"):
                        self._last_written_path = ev["args"].get("path")

                elif t == "tool_result":
                    if self._cur_pill:
                        self.chat.update_tool_card(self._cur_pill)
                        self._cur_pill = None
                    # Auto-reload if agent wrote a currently-open file
                    if hasattr(self, "_last_written_path") and self._last_written_path:
                        self.code_viewer.reload_file(Path(self._last_written_path))
                        self.explorer._refresh_tree()
                        self._last_written_path = None

                elif t == "done":
                    content = ev.get("content", "(no response)")
                    if self.chat._streaming_box:
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
    def _auto_grow_input(self, event=None):
        """Grow the input box up to 5 lines, shrink when text is deleted."""
        line_h = 22   # approx px per line given font size 13
        padding = 12
        max_lines = 5
        # Count actual lines in the widget
        content = self.input_box.get("1.0", "end-1c")
        lines = content.count("\n") + 1
        new_h = min(max_lines, max(1, lines)) * line_h + padding
        new_h = max(new_h, 48)          # minimum height
        self.input_box.configure(height=new_h)

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

    # ── IDE helpers ────────────────────────────────────────────────────────────────
    def _on_cwd_change(self, path: Path):
        """Called whenever the working directory changes (open folder / create folder)."""
        self._cwd = path
        os.chdir(path)
        import agent as _agent_mod
        _agent_mod.CWD = path
        self.sidebar.cwd_lbl.configure(text=str(path))

    def _open_file(self, path: Path):
        """Open a file in the code viewer. Updates context bar and agent CWD hint."""
        self.code_viewer.open_file(path)
        # Update context bar
        self._ctx_file_lbl.configure(text=f"📄 {path.name}  —  {path.parent}")
        # Sync agent working dir so AI can read_file / write_file with relative paths
        self._on_cwd_change(path.parent)

    def _inject_context(self):
        """
        '@' button: injects selected text (or full file) as a code block
        into the chat input box so the user can ask questions about it.
        """
        ctx = self.code_viewer.get_context()
        if not ctx:
            self.chat.append_error("No file open in the editor.")
            return
        selection = self.code_viewer.get_selection()
        snippet  = selection if selection else ctx["content"][:6000]
        tag      = "selection" if selection else "file"
        lang     = ctx["path"].suffix.lstrip(".")
        block = (
            f"\n\n[{tag}: {ctx['path'].name}]\n"
            f"```{lang}\n{snippet}\n```\n"
        )
        # Append to whatever the user has already typed
        cur = self.input_box.get("1.0", "end-1c")
        self.input_box.delete("1.0", "end")
        self.input_box.insert("1.0", cur + block)
        self._auto_grow_input()
        self.input_box.focus_set()

    def _build_send_text(self, user_text: str) -> str:
        """
        Antigravity-style context injection:
        If the user's message doesn't already have a code block and there
        is an open file, silently prepend a compact file context header
        so the AI always knows what's on screen.
        """
        if "```" in user_text:          # user already added context manually
            return user_text
        ctx = self.code_viewer.get_context()
        if not ctx:
            return user_text
        path    = ctx["path"]
        content = ctx["content"]
        lang    = path.suffix.lstrip(".")
        # Only attach first 200 lines to keep context compact
        lines   = content.splitlines()[:200]
        snippet = "\n".join(lines)
        ellipsis = "\n... (truncated)" if len(content.splitlines()) > 200 else ""
        header = (
            f"[Currently open: `{path}`]\n"
            f"```{lang}\n{snippet}{ellipsis}\n```\n\n"
        )
        return header + user_text

    def _review_file(self, path: Path, content: str):
        """Send a file-review request to the AI."""
        prompt = (
            f"Please review this file and list any bugs, issues, or improvements.\n\n"
            f"File: `{path}`\n"
            f"```{path.suffix.lstrip('.')}\n{content[:8000]}\n```"
        )
        self._send_prompt(prompt)

    def _revamp_file(self, path: Path, content: str):
        """Ask the AI to refactor the file and write it back."""
        prompt = (
            f"Please refactor and improve this file completely. "
            f"Show the improved version then call write_file to save it.\n\n"
            f"File: `{path}`\n"
            f"```{path.suffix.lstrip('.')}\n{content[:8000]}\n```"
        )
        self._send_prompt(prompt)

    def _send_prompt(self, text: str):
        """Pre-fill and immediately send a chat message."""
        self.input_box.delete("1.0", "end")
        self.input_box.insert("1.0", text)
        self._send()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n  🦞  Claw Agent Desktop")
    print("  Starting…\n")
    app = ClawApp()
    app.mainloop()
