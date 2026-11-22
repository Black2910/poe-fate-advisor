"""Click-through four-edge highlight for the recommended on-screen Fate card.

The four very small windows cover only the *border* of the card. No game
interaction, reading, click automation or continuous screen polling occurs.
"""
from __future__ import annotations

import math
import sys
import tkinter as tk
from typing import Any

GREEN_FRAME = "#52FF91"


def validated_card_box(result: dict[str, Any]) -> list[float] | None:
    """Return a trustworthy normalized 0..1000 box, or no box at all.

    Refuse uncertain and non-selection screens; especially important for the
    Invoke Fates altar, where a green 'choice' frame would be misleading.
    """
    if result.get("screen_type") != "selection" or result.get("confidence") == "niedrig":
        return None
    best = result.get("best_number")
    try:
        best = int(best)
    except (TypeError, ValueError):
        return None
    if best not in (1, 2, 3):
        return None
    cards = result.get("cards")
    if not isinstance(cards, list):
        return None
    matches = [card for card in cards if isinstance(card, dict)
               and str(card.get("number")) == str(best) and card.get("name")]
    if len(matches) != 1:
        return None
    box = matches[0].get("box")
    if not isinstance(box, list) or len(box) != 4:
        return None
    if any(isinstance(n, bool) or not isinstance(n, (int, float)) or not math.isfinite(n)
           for n in box):
        return None
    x0, y0, x1, y1 = [float(n) for n in box]
    if not (0 <= x0 < x1 <= 1000 and 0 <= y0 < y1 <= 1000):
        return None
    # A genuine full Fate card occupies more than a single UI icon.
    if x1 - x0 < 35 or y1 - y0 < 70:
        return None
    # Avoid obviously oversized regions such as the entire screenshot.
    if x1 - x0 > 650 or y1 - y0 > 900:
        return None
    return [x0, y0, x1, y1]


def screen_card_rect(result: dict[str, Any], capture_region: tuple[int, int, int, int] | None) -> tuple[int, int, int, int] | None:
    """Map normalized bounding box to absolute desktop coordinates.

    If an image was opened from disk, capture_region is None. We must NOT
    claim to know where such a screenshot appears on the live game screen.
    """
    box = validated_card_box(result)
    if box is None or capture_region is None or len(capture_region) != 4:
        return None
    x, y, w, h = capture_region
    if w <= 0 or h <= 0:
        return None
    x0, y0, x1, y1 = box
    left = round(x + x0 * w / 1000)
    top = round(y + y0 * h / 1000)
    width = round((x1 - x0) * w / 1000)
    height = round((y1 - y0) * h / 1000)
    if width < 42 or height < 60:
        return None
    return (left, top, width, height)


class CardMarker:
    """Four unobtrusive, focus-free, click-through Tk top-level edges."""

    def __init__(self, master: tk.Misc, thickness: int = 5):
        self.thickness = thickness
        self._visible = False
        self._box = None
        self.edges: list[tk.Toplevel] = []
        for _ in range(4):
            edge = tk.Toplevel(master)
            edge.withdraw()
            edge.overrideredirect(True)
            edge.configure(bg=GREEN_FRAME)
            edge.attributes("-topmost", True)
            self.edges.append(edge)
            self._make_clickthrough(edge)

    @staticmethod
    def _make_clickthrough(window: tk.Toplevel):
        if sys.platform != "win32":
            return
        # Windows extended styles. Using separate edge-only windows means
        # the interior stays fully click-through even without Win32 support.
        try:
            import ctypes
            from ctypes import wintypes
            user32 = ctypes.windll.user32
            user32.GetParent.argtypes = [wintypes.HWND]
            user32.GetParent.restype = wintypes.HWND
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                getter = user32.GetWindowLongPtrW
                setter = user32.SetWindowLongPtrW
                signed_ptr = ctypes.c_ssize_t
            else:
                getter = user32.GetWindowLongW
                setter = user32.SetWindowLongW
                signed_ptr = ctypes.c_long
            getter.argtypes = [wintypes.HWND, ctypes.c_int]
            getter.restype = signed_ptr
            setter.argtypes = [wintypes.HWND, ctypes.c_int, signed_ptr]
            setter.restype = signed_ptr
            hwnd = user32.GetParent(window.winfo_id()) or window.winfo_id()
            GWL_EXSTYLE = -20
            WS_EX_TRANSPARENT = 0x20
            WS_EX_LAYERED = 0x80000
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_TOOLWINDOW = 0x80
            old = getter(hwnd, GWL_EXSTYLE)
            setter(hwnd, GWL_EXSTYLE, old | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
        except Exception:
            # Don't fail the analyzer when a specific Tk/Windows build differs.
            pass

    def place(self, rect: tuple[int, int, int, int]):
        left, top, width, height = rect
        t = min(self.thickness, max(2, width // 6), max(2, height // 6))
        edge_boxes = [
            (left, top, width, t),
            (left, top + height - t, width, t),
            (left, top + t, t, max(1, height - 2 * t)),
            (left + width - t, top + t, t, max(1, height - 2 * t)),
        ]
        for window, (x, y, w, h) in zip(self.edges, edge_boxes):
            window.geometry(f"{w}x{h}{x:+d}{y:+d}")
        self._box = rect
        self.show()

    def show(self):
        if self._box is None:
            return
        for window in self.edges:
            window.deiconify()
            window.attributes("-topmost", True)
            if sys.platform == "win32":
                try:
                    import ctypes
                    from ctypes import wintypes
                    user32 = ctypes.windll.user32
                    user32.GetParent.argtypes = [wintypes.HWND]
                    user32.GetParent.restype = wintypes.HWND
                    hwnd = user32.GetParent(window.winfo_id()) or window.winfo_id()
                    user32.ShowWindow(hwnd, 8)  # SW_SHOWNA
                except Exception:
                    pass
        self._visible = True

    def hide(self, *, clear: bool = False):
        for window in self.edges:
            window.withdraw()
        self._visible = False
        if clear:
            self._box = None

    @property
    def is_visible(self) -> bool:
        return self._visible

    def destroy(self):
        for window in self.edges:
            window.destroy()
        self.edges.clear()
        self._visible = False
        self._box = None
