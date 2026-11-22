"""Optional Windows system-tray access, so game mode never strands the user.

Tray callbacks enqueue user actions. They never touch Tk or the PoE process.
"""
from __future__ import annotations

import sys
import threading


class TrayController:
    def __init__(self, enqueue):
        self.enqueue = enqueue
        self.icon = None
        self.thread = None

    def start(self):
        if sys.platform != "win32":
            return False
        try:
            import pystray
            from PIL import Image, ImageDraw
            pic = Image.new("RGBA", (64, 64), (14, 24, 37, 255))
            draw = ImageDraw.Draw(pic)
            draw.ellipse((4, 4, 60, 60), outline=(100, 221, 171, 255), width=4)
            draw.line([(18, 15), (18, 49)], fill=(120, 229, 184, 255), width=5)
            draw.line([(18, 17), (45, 17)], fill=(120, 229, 184, 255), width=5)
            draw.line([(18, 32), (39, 32)], fill=(120, 229, 184, 255), width=5)
            item = pystray.MenuItem
            menu = pystray.Menu(
                item("Einstellungen öffnen", lambda _icon, _item: self.enqueue(("action", "settings")), default=True),
                item("Overlay ein / aus (F9)", lambda _icon, _item: self.enqueue(("action", "overlay"))),
                item("Fate-Analyse starten (F8)", lambda _icon, _item: self.enqueue(("action", "capture"))),
                item("Neue Zone / Reset", lambda _icon, _item: self.enqueue(("action", "reset"))),
                item("Beenden", lambda _icon, _item: self.enqueue(("action", "quit"))),
            )
            self.icon = pystray.Icon("poe_fate_advisor", pic, "PoE Fate Advisor", menu)
            self.thread = threading.Thread(target=self.icon.run, daemon=True, name="FateAdvisorTray")
            self.thread.start()
            return True
        except Exception:
            self.icon = None
            return False

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
