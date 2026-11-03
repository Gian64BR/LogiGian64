"""Entry point for source and the Windows executable."""
import argparse
import json
import logging
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnose", action="store_true")
    parser.add_argument("--startup", action="store_true")
    parser.add_argument("--screenshots", type=Path)
    parser.add_argument("--data-dir", type=Path)
    args = parser.parse_args()
    from nexus import windows as win
    if args.diagnose:
        result = {"version": "0.2.7", "devices": [d.to_dict() for d in win.enumerate_devices()],
                  "pointer_speed": win.pointer_speed(), "hardware_plugins": ["G502 HERO host buttons (explicit activation)"], "macro_engine": "Windows Raw Input + SendInput + HID++ button stream",
                  "excluded_virtual_devices": [d.to_dict() for d in win.enumerate_devices(include_virtual=True) if d.virtual]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    from PySide6.QtCore import QTimer, QLockFile, QStandardPaths
    from PySide6.QtWidgets import QApplication, QMessageBox
    from nexus.core import Store
    from nexus.studio import StudioWindow as MainWindow
    from nexus.studio_widgets import STYLE
    app = QApplication(sys.argv[:1])
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("LogiGian64")
    app.setOrganizationName("LogiGian64")
    store = Store(args.data_dir)
    logging.basicConfig(filename=str(store.directory / "nexus.log"), level=logging.WARNING,
                        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")
    lock = QLockFile(str(store.directory / "nexus.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        if not args.startup:
            QMessageBox.information(None, "LogiGian64", "LogiGian64 ya está abierto. Busca el icono de LogiGian64 en la bandeja del sistema.")
        return 0
    app.setStyle("Fusion")
    # Qt's offscreen platform on Windows has no system font database by default.
    if args.screenshots:
        from PySide6.QtGui import QFontDatabase
        for filename in ("segoeui.ttf", "segoeuib.ttf", "seguisym.ttf"):
            QFontDatabase.addApplicationFont(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / filename))
    app.setStyleSheet(STYLE)
    window = MainWindow(store)
    if not args.startup:
        window.show()
    if args.screenshots:
        def capture():
            try:
                args.screenshots.mkdir(parents=True, exist_ok=True)
                window.grab().save(str(args.screenshots / "01-equipo.png"))
                if window.devices:
                    window.open_device(window.devices[0])
                    window.tabs.setCurrentIndex(0)
                    app.processEvents()
                    window.grab().save(str(args.screenshots / "02-asignaciones.png"))
                    window.tabs.setCurrentIndex(1)
                    app.processEvents()
                    window.grab().save(str(args.screenshots / "03-macros.png"))
                window.exit_application()
            except Exception:
                logging.exception("Screenshot QA")
                app.exit(1)
        QTimer.singleShot(600, capture)
    return app.exec()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        import traceback
        path = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "NexusHub"
        path.mkdir(parents=True, exist_ok=True)
        (path / "startup-error.txt").write_text(traceback.format_exc(), encoding="utf-8")
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, "No se pudo iniciar LogiGian64. Detalles en " + str(path / "startup-error.txt"), "LogiGian64", 16)
        except Exception:
            pass
        raise
