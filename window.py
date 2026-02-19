import tkinter as tk


class OverlayWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.on_followup = None  # set by main.py
        self._visible = True
        self._current_prompt = "Interview"
        self._cursor_hidden = False
        self._min_width = 400
        self._min_height = 300
        self._setup_window()
        self._setup_ui()
        self._setup_resize_handles()

    def _setup_window(self):
        from config import WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_X, WINDOW_Y, WINDOW_ALPHA

        self.root.title("Overlay")
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{WINDOW_X}+{WINDOW_Y}")
        self.root.configure(bg="#0d1117")
        self.root.wm_attributes("-topmost", True)
        self.root.wm_attributes("-alpha", WINDOW_ALPHA)
        self.root.overrideredirect(True)  # removes OS title bar

        # CRITICAL: exclude from macOS screen recording
        try:
            self.root.update()  # window must exist before calling AppKit
            from AppKit import NSApp, NSWindowSharingNone
            self._ns_window = NSApp.windows()[-1]
            self._ns_window.setSharingType_(NSWindowSharingNone)
            print("✅ Window excluded from screen capture")
        except Exception as e:
            self._ns_window = None
            print(f"⚠️  Could not exclude from capture: {e}")

        # Cursor hiding on hover 
        self.root.bind("<Enter>", self._on_window_enter)
        self.root.bind("<Leave>", self._on_window_leave)

    def _setup_ui(self):
        # ── Drag bar (top bar) ─────────────────────────────────────────────
        self.drag_bar = tk.Frame(self.root, bg="#161b22", height=28)
        self.drag_bar.pack(fill="x")
        self.drag_bar.bind("<ButtonPress-1>", self._start_drag)
        self.drag_bar.bind("<B1-Motion>", self._drag_window)

        tk.Label(
            self.drag_bar,
            text="  🤖 Interview Assistant",
            bg="#161b22",
            fg="#58d68d",
            font=("Menlo", 11, "bold"),
        ).pack(side="left")

        tk.Button(
            self.drag_bar,
            text="✕",
            bg="#161b22",
            fg="#888888",
            bd=0,
            padx=8,
            activebackground="#ff5f56",
            activeforeground="white",
            command=self.root.quit,
        ).pack(side="right")

        # ── Status bar ────────────────────────────────────────────────────
        self.status_var = tk.StringVar(value="Press Ctrl+Shift+Space to capture")
        tk.Label(
            self.root,
            textvariable=self.status_var,
            bg="#0d1117",
            fg="#666666",
            font=("Menlo", 10),
            anchor="w",
            padx=10,
        ).pack(fill="x", pady=(4, 0))

        # ── Answer text area with scrollbar ──────────────────────────────
        text_frame = tk.Frame(self.root, bg="#0d1117")
        text_frame.pack(fill="both", expand=True)

        scrollbar = tk.Scrollbar(text_frame, orient="vertical")
        scrollbar.pack(side="right", fill="y")

        self.text = tk.Text(
            text_frame,
            bg="#0d1117",
            fg="#c9d1d9",
            font=("Menlo", 12),
            wrap="word",
            bd=0,
            padx=12,
            pady=8,
            insertbackground="white",
            selectbackground="#264f78",
            yscrollcommand=scrollbar.set,
        )
        self.text.pack(side="left", fill="both", expand=True)
        self.text.bind("<Button-1>", self._focus_text)
        scrollbar.config(command=self.text.yview)

        # ── Follow-up input ──────────────────────────────────────────────
        input_frame = tk.Frame(self.root, bg="#161b22")
        input_frame.pack(fill="x")

        self.input_entry = tk.Entry(
            input_frame, bg="#0d1117", fg="#c9d1d9", font=("Menlo", 12),
            insertbackground="white", bd=0, relief="flat",
        )
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(12, 4), pady=6)
        self.input_entry.insert(0, "Ask a follow-up...")
        self.input_entry.bind("<FocusIn>", self._clear_placeholder)
        self.input_entry.bind("<FocusOut>", self._restore_placeholder)
        self.input_entry.bind("<Return>", lambda e: self._on_followup())
        self.input_entry.bind("<Button-1>", self._focus_entry)

        tk.Button(
            input_frame, text="Send", bg="#161b22", fg="#58d68d", bd=0,
            font=("Menlo", 10), command=self._on_followup,
        ).pack(side="right", padx=(0, 8), pady=6)

        # ── Bottom buttons row ───────────────────────────────────────────
        btn_frame = tk.Frame(self.root, bg="#161b22")
        btn_frame.pack(fill="x")

        tk.Button(
            btn_frame,
            text="📋 Copy",
            bg="#161b22",
            fg="#58d68d",
            bd=0,
            padx=10,
            pady=4,
            font=("Menlo", 10),
            command=self._copy_text,
        ).pack(side="left", fill="x", expand=True)

        tk.Button(
            btn_frame,
            text="💾 Save",
            bg="#161b22",
            fg="#58d68d",
            bd=0,
            padx=10,
            pady=4,
            font=("Menlo", 10),
            command=self._save_markdown,
        ).pack(side="left", fill="x", expand=True)

    # ── Drag logic ─────────────────────────────────────────────────────────

    def _start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _drag_window(self, event):
        x = self.root.winfo_x() + event.x - self._drag_x
        y = self.root.winfo_y() + event.y - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    # ── Public API (called from main.py) ────────────────────────────────────

    def set_status(self, msg: str):
        """Thread-safe status update."""
        self.root.after(0, lambda: self.status_var.set(msg))

    def stream_token(self, token: str):
        """Thread-safe: insert token into text area."""
        self.root.after(0, lambda: self._insert(token))

    def _insert(self, token: str):
        at_bottom = self.text.yview()[1] >= 0.95
        self.text.insert("end", token)
        if at_bottom:
            self.text.see("end")

    def clear(self):
        """Thread-safe: clear the text area."""
        self.root.after(0, lambda: self.text.delete("1.0", "end"))

    # ── Placeholder logic ────────────────────────────────────────────────

    def _clear_placeholder(self, event):
        if self.input_entry.get() == "Ask a follow-up...":
            self.input_entry.delete(0, "end")

    def _restore_placeholder(self, event):
        if not self.input_entry.get().strip():
            self.input_entry.insert(0, "Ask a follow-up...")

    def _focus_entry(self, event):
        """Force focus to entry widget (fixes overrideredirect focus issues)."""
        self.root.focus_force()
        self.input_entry.focus_set()

    def _focus_text(self, event):
        """Force focus to text area (fixes overrideredirect focus issues)."""
        self.root.focus_force()
        self.text.focus_set()

    def _on_followup(self):
        text = self.input_entry.get().strip()
        if not text or text == "Ask a follow-up..." or not self.on_followup:
            return
        self.input_entry.delete(0, "end")
        self.on_followup(text)

    def _copy_text(self):
        """Copy all text to clipboard."""
        content = self.text.get("1.0", "end").strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.set_status("✅ Copied to clipboard!")
        self.root.after(2000, self._restore_default_status)

    def _save_markdown(self):
        """Save conversation to markdown file on Desktop."""
        import os
        from datetime import datetime
        content = self.text.get("1.0", "end").strip()
        if not content:
            self.set_status("⚠️ Nothing to save")
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.expanduser(f"~/Desktop/interview_{timestamp}.md")
        header = f"# Interview Notes - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        header += f"**Mode**: {self._current_prompt}\n\n---\n\n"
        with open(filename, "w") as f:
            f.write(header + content)
        self.set_status(f"✅ Saved to {os.path.basename(filename)}")
        self.root.after(2000, self._restore_default_status)

    def _restore_default_status(self):
        """Restore status bar to show current prompt mode."""
        self.status_var.set(f"[{self._current_prompt}] Ctrl+Shift+Space=screenshot  Ctrl+\\=toggle")

    # ── Toggle, Move, Prompt methods ─────────────────────────────────────

    def toggle(self):
        """Toggle window visibility."""
        def _toggle():
            if self._visible:
                self.root.withdraw()
                self._visible = False
            else:
                self.root.deiconify()
                self._visible = True
        self.root.after(0, _toggle)

    def move(self, dx: int, dy: int):
        """Move window by dx, dy pixels."""
        def _move():
            x = self.root.winfo_x() + dx
            y = self.root.winfo_y() + dy
            self.root.geometry(f"+{x}+{y}")
        self.root.after(0, _move)

    def set_prompt_mode(self, mode: str):
        """Update current prompt mode and status bar."""
        def _set():
            self._current_prompt = mode
            self._restore_default_status()
        self.root.after(0, _set)

    def get_prompt_mode(self) -> str:
        return self._current_prompt

    # ── Resize handles py─────────────────────────────────

    def _setup_resize_handles(self):
        """Add resize handles to corners and edges."""
        handle_size = 8
        handle_color = "#161b22"

        # Bottom-right corner (main resize)
        self._resize_br = tk.Frame(self.root, bg=handle_color, cursor="bottom_right_corner",
                                    width=handle_size, height=handle_size)
        self._resize_br.place(relx=1.0, rely=1.0, anchor="se")
        self._resize_br.bind("<ButtonPress-1>", self._start_resize)
        self._resize_br.bind("<B1-Motion>", self._do_resize)

        # Bottom edge
        self._resize_b = tk.Frame(self.root, bg=handle_color, cursor="sb_v_double_arrow",
                                   height=handle_size)
        self._resize_b.place(relx=0.5, rely=1.0, anchor="s", relwidth=0.8)
        self._resize_b.bind("<ButtonPress-1>", self._start_resize_v)
        self._resize_b.bind("<B1-Motion>", self._do_resize_v)

        # Right edge
        self._resize_r = tk.Frame(self.root, bg=handle_color, cursor="sb_h_double_arrow",
                                   width=handle_size)
        self._resize_r.place(relx=1.0, rely=0.5, anchor="e", relheight=0.8)
        self._resize_r.bind("<ButtonPress-1>", self._start_resize_h)
        self._resize_r.bind("<B1-Motion>", self._do_resize_h)

    def _start_resize(self, event):
        self._resize_start_x = event.x_root
        self._resize_start_y = event.y_root
        self._resize_start_w = self.root.winfo_width()
        self._resize_start_h = self.root.winfo_height()

    def _do_resize(self, event):
        dx = event.x_root - self._resize_start_x
        dy = event.y_root - self._resize_start_y
        new_w = max(self._min_width, self._resize_start_w + dx)
        new_h = max(self._min_height, self._resize_start_h + dy)
        self.root.geometry(f"{new_w}x{new_h}")

    def _start_resize_v(self, event):
        self._resize_start_y = event.y_root
        self._resize_start_h = self.root.winfo_height()

    def _do_resize_v(self, event):
        dy = event.y_root - self._resize_start_y
        new_h = max(self._min_height, self._resize_start_h + dy)
        self.root.geometry(f"{self.root.winfo_width()}x{new_h}")

    def _start_resize_h(self, event):
        self._resize_start_x = event.x_root
        self._resize_start_w = self.root.winfo_width()

    def _do_resize_h(self, event):
        dx = event.x_root - self._resize_start_x
        new_w = max(self._min_width, self._resize_start_w + dx)
        self.root.geometry(f"{new_w}x{self.root.winfo_height()}")

    # ── Cursor hiding  ──────────────────────────────

    def _on_window_enter(self, event):
        """Optionally hide cursor when mouse enters window."""
        if self._cursor_hidden:
            self.root.config(cursor="none")

    def _on_window_leave(self, event):
        """Restore cursor when mouse leaves window."""
        self.root.config(cursor="")

    def toggle_cursor(self, hidden: bool = None):
        """Toggle or set cursor visibility for stealth mode."""
        if hidden is None:
            self._cursor_hidden = not self._cursor_hidden
        else:
            self._cursor_hidden = hidden
        if not self._cursor_hidden:
            self.root.config(cursor="")