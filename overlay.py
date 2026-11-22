"""Draggable, compact, click-optional Windows overlay for PoE Fate Advisor.

No capture, process inspection, or game interaction is performed here.
"""
from __future__ import annotations

import sys
import tkinter as tk
from selection_validation import position_label
from app_updates import VERSION
from typing import Callable

BG = "#0c1421"
PANEL = "#152238"
PANEL2 = "#1b2c44"
BORDER = "#38506b"
TEXT = "#eff5ff"
MUTED = "#acbfd8"
GREEN = "#77e4b5"
YELLOW = "#f0c276"
RED = "#f28d8d"
WIDTH = 384


def short_text(value: object, length: int = 160) -> str:
    """Keep cards unobtrusive and don't inject free-form LLM text as UI controls."""
    value = " ".join(str(value or "").split())
    return value if len(value) <= length else value[:length - 1].rstrip() + "…"


def overlay_summary(result: dict) -> dict:
    """Convert a validated AI result into safe display text; no guessing on low confidence."""
    kind = result.get("screen_type", "unknown")
    confidence = result.get("confidence", "niedrig")
    explain = result.get("recommendation", "")
    uncertain = result.get("uncertainty", "")
    if kind == "selection" and result.get("visual_verification") == "mismatch":
        return {"title": "Karten nicht sicher erkannt",
                "detail": short_text(uncertain or explain, 150),
                "sub": short_text("Grund: " + (uncertain or "Bildprüfung unklar"), 103), "color": YELLOW,
                "can_save": False}
    if kind == "selection":
        number = result.get("best_number", 0)
        card = next((c for c in result.get("cards", []) if isinstance(c, dict)
                     and str(c.get("number")) == str(number)), {})
        if not number or not card or not card.get("name"):
            return {"title": "Auswahl unklar", "detail": "F8 erneut mit vollständig sichtbaren Karten.",
                    "sub": "Keine verlässliche Kartennummer", "color": YELLOW, "can_save": False}
        pos = position_label(int(number), len(result.get("cards", [])))
        if confidence == "niedrig":
            return {"title": f"Prüfen: {pos} · {short_text(card['name'], 32)}",
                    "detail": short_text(explain or uncertain, 150),
                    "sub": "Geringe Erkennungssicherheit · selbst prüfen", "color": YELLOW,
                    "can_save": True}
        reward = short_text(card.get("rewards", "Belohnung unbekannt"), 56)
        danger = short_text(card.get("danger", "?"), 18)
        return {"title": f"{pos} · {short_text(card['name'], 34)}",
                "detail": short_text(explain, 168),
                "sub": f"Loot: {reward}   ·   Risiko: {danger}   ·   KI: {confidence}",
                "color": GREEN, "can_save": True}
    if kind == "invocation":
        status = {"empty": "2 Fates gesammelt – noch nicht eingesetzt",
                  "one": "Bossaltar – 1 Fate eingesetzt",
                  "merged": "Bossaltar – gleiche Fates verschmolzen",
                  "other": "Bossaltar erkannt"}.get(result.get("invocation_state"), "Bossaltar erkannt")
        return {"title": "BOSSALTAR", "detail": short_text(explain, 180), "sub": status,
                "color": YELLOW, "can_save": False}
    return {"title": "Fate-Fenster nicht erkannt", "detail": short_text(explain or uncertain, 170),
            "sub": "Tooltip und alle Karten sichtbar machen", "color": YELLOW, "can_save": False}


class FateOverlay(tk.Toplevel):
    """Always-on-top, draggable, optionally compact panel.

    The user always makes the actual choice inside PoE. Save is explicitly
    triggered *after* doing that, either via F6 or the overlay button.
    """

    def __init__(self, master: tk.Misc, on_scan: Callable, on_save: Callable,
                 on_reset: Callable, on_settings: Callable, on_update: Callable,
                 *, geometry: tuple[int, int] | None = None, compact: bool = False,
                 opacity: float = .95, on_visibility: Callable[[bool], None] | None = None):
        super().__init__(master)
        self.withdraw()
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg=BG, highlightthickness=0)
        self.opacity = max(.70, min(1.0, float(opacity)))
        self.attributes("-alpha", self.opacity)
        self._on_scan, self._on_save = on_scan, on_save
        self._on_reset, self._on_settings, self._on_update = on_reset, on_settings, on_update
        self._on_visibility = on_visibility
        self._drag_start = None
        self._compact = bool(compact)
        self._user_visible = True
        self._capture_was_visible = False
        self._save_allowed = False
        self._build()
        width, height = self._size()
        if geometry is None:
            x = max(15, self.winfo_screenwidth() - width - 38)
            y = 175
        else:
            x, y = int(geometry[0]), int(geometry[1])
        self.geometry(f"{width}x{height}{x:+d}{y:+d}")
        self._set_windows_no_activate()
        self.show()
        self.set_ready()

    def _size(self) -> tuple[int, int]:
        return WIDTH, 179 if self._compact else 285

    def _label(self, parent, value: str, font: tuple, fg=TEXT, **kwargs):
        return tk.Label(parent, text=value, bg=parent.cget("bg"), fg=fg,
                        font=font, anchor="w", **kwargs)

    def _button(self, parent, title, action, bg=PANEL2, fg=TEXT, width=None):
        return tk.Button(parent, text=title, command=action, bg=bg, fg=fg,
                         activebackground="#345072", activeforeground="white",
                         disabledforeground="#70849e", relief="flat", borderwidth=0,
                         cursor="hand2", font=("Segoe UI", 9, "bold"),
                         padx=7, pady=5, takefocus=False, width=width)

    def _build(self):
        outer = tk.Frame(self, bg=BG, highlightbackground=BORDER,
                         highlightthickness=1)
        outer.pack(fill="both", expand=True)
        header = tk.Frame(outer, bg=PANEL, height=36)
        header.pack(fill="x")
        header.pack_propagate(False)
        dot = self._label(header, "●", ("Segoe UI", 11), fg=GREEN)
        dot.pack(side="left", padx=(12, 5))
        caption = self._label(header, "FATE ADVISOR v"+VERSION, ("Segoe UI", 10, "bold"))
        caption.pack(side="left")
        self._button(header, "⚙", self._on_settings, bg=PANEL).pack(side="right", padx=(0, 6))
        self._button(header, "—", self.hide, bg=PANEL).pack(side="right")
        self._compact_button = self._button(header, "▤", self.toggle_compact, bg=PANEL)
        self._compact_button.pack(side="right")
        for item in (header, dot, caption):
            item.bind("<ButtonPress-1>", self._drag_begin)
            item.bind("<B1-Motion>", self._drag_move)
            item.bind("<ButtonRelease-1>", self._drag_end)

        body = tk.Frame(outer, bg=BG, padx=13, pady=9)
        body.pack(fill="both", expand=True)
        self.status = self._label(body, "BEREIT", ("Segoe UI", 8, "bold"), fg=GREEN)
        self.status.pack(fill="x")
        self.title_label = self._label(body, "F8 · Fate scannen", ("Segoe UI", 16, "bold"))
        self.title_label.pack(fill="x", pady=(2, 4))
        self.subtitle = self._label(body, "F6 merken · F9 anzeigen/verbergen", ("Segoe UI", 9),
                                    fg=MUTED, wraplength=354, justify="left")
        self.subtitle.pack(fill="x")
        self.extended = tk.Frame(body, bg=BG)
        self.extended.pack(fill="x", pady=(7, 0))
        self.detail = self._label(self.extended, "Ein Tastendruck = ein Screenshot und eine KI-Auswertung.",
                                  ("Segoe UI", 10), fg=TEXT, wraplength=345, justify="left")
        self.detail.pack(fill="x", anchor="nw")
        self.prior = self._label(self.extended, "In dieser Zone: —", ("Segoe UI", 9),
                                 fg=MUTED, wraplength=345, justify="left")
        self.prior.pack(fill="x", pady=(7, 0))

        buttons = tk.Frame(body, bg=BG)
        buttons.pack(side="bottom", fill="x", pady=(7, 0))
        self.scan_btn = self._button(buttons, "F8  Analysieren", self._on_scan, bg="#245c66")
        self.scan_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.save_btn = self._button(buttons, "F6  Gemerkt", self._on_save, bg="#1d765b")
        self.save_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self._button(buttons, "↻", self._on_reset, width=2).pack(side="right")
        self._apply_compact()

    def _apply_compact(self):
        if self._compact:
            self.extended.pack_forget()
            self._compact_button.configure(text="▣")
        else:
            self.extended.pack(fill="x", pady=(7, 0), before=self.extended.master.winfo_children()[-1])
            self._compact_button.configure(text="▤")
        width, height = self._size()
        self.geometry(f"{width}x{height}")

    def toggle_compact(self):
        self._compact = not self._compact
        self._apply_compact()
        self._on_update()

    def set_opacity(self, value: float):
        self.opacity = max(.70, min(1.0, float(value)))
        self.attributes("-alpha", self.opacity)
        self._on_update()

    def _drag_begin(self, event):
        self._drag_start = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _drag_move(self, event):
        if self._drag_start:
            x = event.x_root - self._drag_start[0]
            y = event.y_root - self._drag_start[1]
            self.geometry(f"+{x}+{y}" if x >= 0 and y >= 0 else f"{x:+d}{y:+d}")

    def _drag_end(self, _event):
        self._drag_start = None
        self._on_update()

    def _set_windows_no_activate(self):
        """Best-effort no-activation flag so displaying a result doesn't alt-tab from PoE."""
        if sys.platform != "win32":
            return
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            user32.GetParent.argtypes = [wintypes.HWND]
            user32.GetParent.restype = wintypes.HWND
            GetWindowLongPtr = user32.GetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else user32.GetWindowLongW
            SetWindowLongPtr = user32.SetWindowLongPtrW if ctypes.sizeof(ctypes.c_void_p) == 8 else user32.SetWindowLongW
            GetWindowLongPtr.argtypes = [wintypes.HWND, ctypes.c_int]
            GetWindowLongPtr.restype = ctypes.c_ssize_t
            SetWindowLongPtr.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
            hwnd = user32.GetParent(self.winfo_id()) or self.winfo_id()
            GWL_EXSTYLE = -20
            WS_EX_NOACTIVATE = 0x08000000
            old = GetWindowLongPtr(hwnd, GWL_EXSTYLE)
            SetWindowLongPtr(hwnd, GWL_EXSTYLE, old | WS_EX_NOACTIVATE)
        except Exception:
            # Still functional; some Windows Tk implementations may focus briefly.
            pass

    def show(self):
        self._user_visible = True
        self.deiconify()
        self.attributes("-topmost", True)
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes
                user32 = ctypes.windll.user32
                user32.GetParent.argtypes = [wintypes.HWND]
                user32.GetParent.restype = wintypes.HWND
                hwnd = user32.GetParent(self.winfo_id()) or self.winfo_id()
                user32.ShowWindow(hwnd, 8)  # SW_SHOWNA
            except Exception:
                pass
        if self._on_visibility:
            self._on_visibility(True)

    def hide(self):
        self._user_visible = False
        self.withdraw()
        if self._on_visibility:
            self._on_visibility(False)

    def toggle_visibility(self):
        if self._user_visible:
            self.hide()
        else:
            self.show()

    def suspend_for_capture(self):
        self._capture_was_visible = self._user_visible
        if self._capture_was_visible:
            self.withdraw()

    def resume_after_capture(self):
        if self._capture_was_visible and self._user_visible:
            self.show()
        self._capture_was_visible = False

    def set_ready(self):
        self.set_message("BEREIT", "F8 · Fate scannen", "F6 merken · F9 anzeigen/verbergen",
                         "Ein Tastendruck = ein Screenshot und eine KI-Auswertung.", GREEN, can_save=False)

    def set_message(self, status: str, title: str, subtitle: str,
                    detail: str, color: str, *, can_save: bool = False):
        self.status.configure(text=short_text(status, 26), fg=color)
        self.title_label.configure(text=short_text(title, 44), fg=color)
        self.subtitle.configure(text=short_text(subtitle, 125))
        self.detail.configure(text=short_text(detail, 220))
        self._save_allowed = can_save
        self.save_btn.configure(state="normal" if can_save else "disabled")

    def set_busy(self, message: str):
        self.set_message("ANALYSE", "Fates werden geprüft …",
                         "Screenshot erfasst · KI wertet aus", message, YELLOW, can_save=False)
        self.scan_btn.configure(state="disabled")

    def set_result(self, result: dict):
        summary = overlay_summary(result)
        status = "EMPFEHLUNG" if result.get("screen_type") == "selection" else "STATUS"
        if result.get("confidence") == "niedrig":
            status = "BITTE PRÜFEN"
        self.set_message(status, summary["title"], summary["sub"],
                         summary["detail"], summary["color"], can_save=summary["can_save"])
        self.scan_btn.configure(state="normal")

    def set_error(self, reason: str):
        self.set_message("FEHLER", "Analyse fehlgeschlagen", "Einstellungen / API prüfen",
                         short_text(reason, 170), RED, can_save=False)
        self.scan_btn.configure(state="normal")

    def set_prior(self, names: list[str]):
        if not names:
            label = "In dieser Zone: —"
        else:
            label = "In dieser Zone: " + " + ".join(names[-3:])
        self.prior.configure(text=short_text(label, 110))

    @property
    def compact(self) -> bool:
        return self._compact

    @property
    def position(self) -> tuple[int, int]:
        return self.winfo_x(), self.winfo_y()

    @property
    def is_visible(self) -> bool:
        return self._user_visible
