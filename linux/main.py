"""Linux entry point. --diagnose never takes hardware ownership."""
import argparse
import json
import logging
import os
from pathlib import Path
import signal
import sys

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--diagnose',action='store_true')
    parser.add_argument('--startup',action='store_true')
    parser.add_argument('--screenshots',type=Path)
    parser.add_argument('--data-dir',type=Path)
    args=parser.parse_args()
    from nexus import __version__
    from nexus import linux_backend
    if args.diagnose:
        result=linux_backend.diagnostics()
        result.update(version=__version__,platform='Linux',engine='evdev + uinput + HID++')
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 1 if result.get('error') else 0
    from PySide6.QtCore import QTimer,QLockFile
    from PySide6.QtWidgets import QApplication,QMessageBox,QSystemTrayIcon
    from nexus.core import Store
    from nexus.studio import StudioWindow
    from nexus.studio_widgets import STYLE
    app=QApplication(sys.argv[:1]);app.setQuitOnLastWindowClosed(False)
    app.setApplicationName('LogiGian64');app.setOrganizationName('LogiGian64')
    store=Store(args.data_dir)
    logging.basicConfig(filename=str(store.directory/'nexus.log'),level=logging.WARNING,format='%(asctime)s %(levelname)s %(message)s',encoding='utf-8')
    lock=QLockFile(str(store.directory/'nexus.lock'));lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        if not args.startup:QMessageBox.information(None,'LogiGian64','El programa ya esta abierto. Revisa la bandeja del sistema.')
        return 0
    app.setStyle('Fusion');app.setStyleSheet(STYLE)
    window=StudioWindow(store)
    heartbeat=QTimer();heartbeat.timeout.connect(lambda:None);heartbeat.start(200)
    for number in (signal.SIGTERM,signal.SIGINT):signal.signal(number,lambda *_:window.installer_shutdown())
    if not args.screenshots:window.enable_auto_g502()
    if not args.startup:window.show()
    elif not QSystemTrayIcon.isSystemTrayAvailable():window.showMinimized()
    if args.screenshots:
        def capture():
            args.screenshots.mkdir(parents=True,exist_ok=True)
            window.grab().save(str(args.screenshots/'01-equipo.png'))
            window.go_profiles();app.processEvents();window.grab().save(str(args.screenshots/'02-perfiles.png'))
            window.exit_application()
        QTimer.singleShot(500,capture)
    return app.exec()

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception:
        import traceback
        path=Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'logigian64'
        path.mkdir(parents=True,exist_ok=True);(path/'startup-error.txt').write_text(traceback.format_exc(),encoding='utf-8')
        raise
