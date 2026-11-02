# Third-party components

LogiGian64's original source code is MIT licensed. It does not include Logitech code,
logos, images or binaries. Peripheral illustrations are drawn in the application.

- Python 3.11: Python Software Foundation license, https://docs.python.org/3/license.html
- Qt for Python / PySide6 6.12.0 and Shiboken6: LGPL-3.0-only / GPL-3.0 alternatives and
  component-specific Qt licenses. This build uses the LGPL option for Qt Core, GUI
  and Widgets. https://www.qt.io/licensing/open-source-lgpl-obligations
  Corresponding upstream sources: https://code.qt.io/cgit/pyside/pyside-setup.git/
  and https://code.qt.io/cgit/qt/ . Release tag v6.12.0. License texts bundled in licenses/.
- PyInstaller 6.22.2 bootloader: GPL with the PyInstaller bootloader exception.
  https://pyinstaller.org/en/stable/license.html

The complete Nexus source and build instructions are distributed alongside the
executable so users can modify and rebuild it, including replacing its Qt libraries.
The executable uses PyInstaller one-file extraction and dynamically loaded Qt DLLs.
No Qt library source modifications were made.

- HIDAPI Python binding 0.15.0 / HIDAPI: BSD-3-Clause option; license texts in licenses/hidapi-*.txt. https://github.com/trezor/cython-hidapi and https://github.com/libusb/hidapi .
- Optional Logitech device photos are read from the user's existing G HUB installation at runtime. They are not part of this distribution; ownership remains with Logitech.

- KNUP KP-V84 top and side illustrations were generated from user-supplied visual references for this project. KNUP branding identifies the depicted device. These illustrations do not imply an official KNUP integration.
