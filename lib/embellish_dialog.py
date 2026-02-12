"""Tkinter modal dialog for configuring and launching LLM embellishment."""

import os
import threading
import tkinter as tk
from tkinter import ttk

import lib.embellish
from lib.embellish import PROVIDER_MODELS, EmbellishmentScope
from lib.embellish_settings import load_settings, save_settings, settings_path


class EmbellishDialog:
    """Modal dialog for configuring embellishment parameters.

    Opens as a Toplevel window; blocks until the user closes it.
    The dialog handles threading internally.  On success, ``self.results``
    holds the list of EmbellishmentResult objects; on cancel/error it is
    None.
    """

    TONES = [
        "Classic D&D",
        "Grimdark",
        "Whimsical",
        "Lovecraftian",
        "Custom",
    ]

    def __init__(self, parent, df):
        self.df = df
        self.results = None
        self._cancel_event = threading.Event()

        self.win = tk.Toplevel(parent)
        self.win.title("Embellish Dungeon")
        self.win.transient(parent)
        self.win.grab_set()
        self.win.resizable(False, False)
        self.win.protocol("WM_DELETE_WINDOW", self._on_cancel)

        settings = load_settings()

        # --- Service section ---
        svc_frame = ttk.LabelFrame(self.win, text="Service", padding=8)
        svc_frame.pack(fill="x", padx=10, pady=(10, 4))

        ttk.Label(svc_frame, text="Provider:").grid(
            row=0, column=0, sticky="w"
        )
        self.provider_var = tk.StringVar(
            value=settings.get("provider", "Anthropic")
        )
        provider_cb = ttk.Combobox(
            svc_frame,
            textvariable=self.provider_var,
            values=list(PROVIDER_MODELS.keys()),
            state="readonly",
            width=20,
        )
        provider_cb.grid(row=0, column=1, sticky="w", padx=4)
        provider_cb.bind("<<ComboboxSelected>>", self._on_provider_changed)

        ttk.Label(svc_frame, text="API Key:").grid(row=1, column=0, sticky="w")
        self.api_key_var = tk.StringVar(value=settings.get("api_key", ""))
        self.api_key_entry = ttk.Entry(
            svc_frame, textvariable=self.api_key_var, width=40, show="*"
        )
        self.api_key_entry.grid(row=1, column=1, sticky="w", padx=4)
        self.api_key_var.trace_add(
            "write", lambda *_: self._update_estimates()
        )
        self.show_key_var = tk.BooleanVar(value=False)
        show_key_cb = tk.Checkbutton(
            svc_frame,
            text="Show",
            variable=self.show_key_var,
            command=self._toggle_key_visibility,
        )
        show_key_cb.grid(row=1, column=2, sticky="w")

        ttk.Label(svc_frame, text="Model:").grid(row=2, column=0, sticky="w")
        self.model_var = tk.StringVar(value=settings.get("model", ""))
        self.model_cb = ttk.Combobox(
            svc_frame,
            textvariable=self.model_var,
            state="readonly",
            width=30,
        )
        self.model_cb.grid(row=2, column=1, sticky="w", padx=4)
        self._populate_models()

        # --- Config path ---
        path_frame = ttk.Frame(self.win, padding=(10, 2))
        path_frame.pack(fill="x")
        ttk.Label(
            path_frame,
            text=f"Settings file: {settings_path()}",
            foreground="gray",
        ).pack(anchor="w")

        # --- Tone section ---
        tone_frame = ttk.LabelFrame(self.win, text="Tone", padding=8)
        tone_frame.pack(fill="x", padx=10, pady=4)

        self.tone_var = tk.StringVar(value=settings.get("tone", "Classic D&D"))
        tone_cb = ttk.Combobox(
            tone_frame,
            textvariable=self.tone_var,
            values=self.TONES,
            state="readonly",
            width=20,
        )
        tone_cb.pack(anchor="w")
        tone_cb.bind("<<ComboboxSelected>>", self._on_tone_changed)

        self.custom_tone_var = tk.StringVar(
            value=settings.get("custom_tone", "")
        )
        self.custom_tone_entry = ttk.Entry(
            tone_frame, textvariable=self.custom_tone_var, width=50
        )
        if self.tone_var.get() == "Custom":
            self.custom_tone_entry.pack(anchor="w", pady=(4, 0))

        # --- Scope section ---
        scope_frame = ttk.LabelFrame(self.win, text="Scope", padding=8)
        scope_frame.pack(fill="x", padx=10, pady=4)

        self.scope_rooms_var = tk.BooleanVar(
            value=settings.get("scope_rooms", True)
        )
        self.scope_corridors_var = tk.BooleanVar(
            value=settings.get("scope_corridors", True)
        )
        self.scope_traps_var = tk.BooleanVar(
            value=settings.get("scope_traps", True)
        )
        self.scope_books_var = tk.BooleanVar(
            value=settings.get("scope_books", True)
        )

        self.scope_labels = {}
        for i, (label, var) in enumerate(
            [
                ("Rooms", self.scope_rooms_var),
                ("Corridors", self.scope_corridors_var),
                ("Traps", self.scope_traps_var),
                ("Books", self.scope_books_var),
            ]
        ):
            cb = tk.Checkbutton(
                scope_frame,
                text=label,
                variable=var,
                command=self._update_estimates,
            )
            cb.grid(row=i, column=0, sticky="w")
            est_label = ttk.Label(scope_frame, text="", foreground="gray")
            est_label.grid(row=i, column=1, sticky="w", padx=(10, 0))
            self.scope_labels[label.lower()] = est_label

        # --- Summary ---
        self.summary_var = tk.StringVar(value="")
        summary_label = ttk.Label(
            self.win,
            textvariable=self.summary_var,
            padding=(10, 4),
        )
        summary_label.pack(fill="x")

        # --- Progress section (hidden until embellishment starts) ---
        self.progress_frame = ttk.LabelFrame(
            self.win, text="Progress", padding=8
        )

        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            variable=self.progress_var,
            maximum=100,
            length=350,
        )
        self.progress_bar.pack(fill="x", pady=(0, 4))

        self.progress_status_var = tk.StringVar(value="")
        ttk.Label(
            self.progress_frame,
            textvariable=self.progress_status_var,
        ).pack(anchor="w")

        self.progress_log = tk.Text(
            self.progress_frame,
            height=8,
            width=55,
            state="disabled",
            wrap=tk.WORD,
        )
        self.progress_log.pack(fill="both", pady=(4, 0))

        # --- Buttons ---
        btn_frame = ttk.Frame(self.win, padding=8)
        btn_frame.pack(fill="x")
        self.verbose_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            btn_frame,
            text="Show details",
            variable=self.verbose_var,
        ).pack(side="left", padx=4)
        self.embellish_btn = ttk.Button(
            btn_frame, text="Embellish", command=self._on_embellish
        )
        self.embellish_btn.pack(side="right", padx=4)
        self.cancel_btn = ttk.Button(
            btn_frame, text="Cancel", command=self._on_cancel
        )
        self.cancel_btn.pack(side="right", padx=4)

        self._update_estimates()

    # ---- helpers ----

    def _log(self, text):
        """Append text to the progress log."""
        self.progress_log.config(state="normal")
        self.progress_log.insert(tk.END, text + "\n")
        self.progress_log.see(tk.END)
        self.progress_log.config(state="disabled")

    def _toggle_key_visibility(self):
        self.api_key_entry.config(show="" if self.show_key_var.get() else "*")

    def _on_provider_changed(self, event=None):
        self._populate_models()
        self._update_estimates()

    def _populate_models(self):
        provider = self.provider_var.get()
        models = PROVIDER_MODELS.get(provider, [])
        labels = [m["label"] for m in models]
        self.model_cb["values"] = labels
        current = self.model_var.get()
        if current not in labels and labels:
            self.model_cb.current(0)

    def _get_model_id(self):
        provider = self.provider_var.get()
        models = PROVIDER_MODELS.get(provider, [])
        label = self.model_var.get()
        for m in models:
            if m["label"] == label:
                return m["id"]
        return models[0]["id"] if models else ""

    def _on_tone_changed(self, event=None):
        if self.tone_var.get() == "Custom":
            self.custom_tone_entry.pack(anchor="w", pady=(4, 0))
        else:
            self.custom_tone_entry.pack_forget()

    def _current_scope(self):
        return EmbellishmentScope(
            rooms=self.scope_rooms_var.get(),
            corridors=self.scope_corridors_var.get(),
            traps=self.scope_traps_var.get(),
            books=self.scope_books_var.get(),
        )

    def _update_estimates(self):
        scope = self._current_scope()
        model_id = self._get_model_id()
        elements = scope.count_elements(self.df)

        for etype, label_key in [
            ("room", "rooms"),
            ("corridor", "corridors"),
            ("trap", "traps"),
            ("book", "books"),
        ]:
            count = elements.get(etype, 0)
            if count > 0:
                sub_scope = EmbellishmentScope(
                    rooms=(etype == "room"),
                    corridors=(etype == "corridor"),
                    traps=(etype == "trap"),
                    books=(etype == "book"),
                )
                cost = sub_scope.estimate_cost_usd(self.df, model_id)
                self.scope_labels[label_key].config(
                    text=f"({count} items, ~${cost:.3f})"
                )
            else:
                self.scope_labels[label_key].config(text="(0 items)")

        total_calls = scope.count_api_calls(self.df)
        total_cost = scope.estimate_cost_usd(self.df, model_id)
        total_time = scope.estimate_time_seconds(self.df)
        self.summary_var.set(
            f"Estimated total: {total_calls} API calls, "
            f"~${total_cost:.2f}, ~{total_time:.0f}s"
        )

        has_key = bool(self.api_key_var.get().strip())
        has_scope = total_calls > 0
        state = "normal" if (has_key and has_scope) else "disabled"
        self.embellish_btn.config(state=state)

    # ---- actions ----

    def _on_embellish(self):
        tone = self.tone_var.get()
        if tone == "Custom":
            tone = self.custom_tone_var.get() or "Classic D&D"

        settings = {
            "provider": self.provider_var.get(),
            "model": self.model_var.get(),
            "api_key": self.api_key_var.get().strip(),
            "tone": self.tone_var.get(),
            "custom_tone": self.custom_tone_var.get(),
            "scope_rooms": self.scope_rooms_var.get(),
            "scope_corridors": self.scope_corridors_var.get(),
            "scope_traps": self.scope_traps_var.get(),
            "scope_books": self.scope_books_var.get(),
        }
        save_settings(settings)

        scope = lib.embellish.EmbellishmentScope(
            rooms=settings["scope_rooms"],
            corridors=settings["scope_corridors"],
            traps=settings["scope_traps"],
            books=settings["scope_books"],
        )
        provider = lib.embellish.AnthropicProvider(
            api_key=settings["api_key"],
            model=self._get_model_id(),
        )

        # Show progress panel and disable controls
        self.progress_frame.pack(
            fill="x", padx=10, pady=4, before=self.embellish_btn.master
        )
        self.embellish_btn.config(state="disabled")
        self.cancel_btn.config(text="Stop")
        self.progress_var.set(0.0)
        self.progress_status_var.set("Starting...")
        self._cancel_event.clear()

        def progress_callback(completed, total, result):
            def _update():
                pct = (completed / total * 100) if total else 0
                self.progress_var.set(pct)
                name = result.element_name
                if self.verbose_var.get():
                    elapsed = f"{result.elapsed_seconds:.1f}s"
                    self._log(f"--- {name} ({elapsed}) ---")
                    if result.error:
                        self._log(f"[Error] {result.error}")
                    else:
                        sys_short = (result.system_prompt or "")[:100]
                        self._log(f"[System] {sys_short}")
                        self._log(f"[Prompt] {result.user_prompt}")
                        self._log(f"[Response] {result.flavor_text}")
                else:
                    if result.error:
                        self._log(f"  ERROR  {name}: {result.error}")
                    else:
                        self._log(f"  [{completed}/{total}] {name}")
                self.progress_status_var.set(
                    f"{completed} / {total} completed"
                )

            self.win.after(0, _update)

        def _run():
            results, fatal_error = lib.embellish.embellish_dungeon(
                self.df,
                scope,
                provider,
                tone,
                progress_callback=progress_callback,
                cancel_event=self._cancel_event,
            )

            log_path = None
            if results:
                try:
                    log_path = lib.embellish.write_log_file(results)
                except Exception:
                    pass

            def _finish():
                if self._cancel_event.is_set() and fatal_error:
                    self.progress_status_var.set("Stopped due to error")
                    self._log(f"\n{fatal_error}")
                    if log_path:
                        rel = os.path.relpath(
                            log_path, lib.embellish.COC_ROOT_DIR
                        )
                        self._log(f"Log file: {rel}")
                    self.cancel_btn.config(
                        text="Close", command=self._on_cancel
                    )
                elif self._cancel_event.is_set():
                    self.progress_status_var.set("Cancelled")
                    if log_path:
                        rel = os.path.relpath(
                            log_path, lib.embellish.COC_ROOT_DIR
                        )
                        self._log(f"Log file: {rel}")
                    self.cancel_btn.config(
                        text="Close", command=self._on_cancel
                    )
                else:
                    num_ok = sum(
                        1 for r in results if r.flavor_text is not None
                    )
                    status = f"Done! {num_ok}/{len(results)} succeeded"
                    self.progress_status_var.set(status)
                    self._log(
                        f"\nComplete: {num_ok} embellishments generated."
                    )
                    if log_path:
                        rel = os.path.relpath(
                            log_path, lib.embellish.COC_ROOT_DIR
                        )
                        self._log(f"Log file: {rel}")
                    self.results = results
                    self.cancel_btn.config(
                        text="Close", command=self._on_cancel
                    )

            self.win.after(0, _finish)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

    def _on_cancel(self):
        self._cancel_event.set()
        self.win.destroy()

    def show(self):
        """Block until the dialog closes; return results list or None."""
        self.win.wait_window()
        return self.results
