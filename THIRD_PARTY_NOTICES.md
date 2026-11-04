# Third-party components

LogiGian64's original source code is MIT licensed. It does not include Logitech executable code or binaries. Product photographs
retain their owners' rights and are not covered by the MIT source-code license.

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
- Optional Logitech device photos are read from the user's existing G HUB installation at runtime. The optional G HUB files are not distributed. The independent product views listed below are included; ownership remains with Logitech.

- KNUP KP-V84 top and side illustrations were generated from user-supplied visual references for this project. KNUP branding identifies the depicted device. These illustrations do not imply an official KNUP integration.

- Redragon KUMARA K552RGB-1 keyboard photograph: supplied by the user for this
  application's device view. The original JPEG is included without modification;
  the UI frames its keyboard body. Redragon branding identifies the depicted
  product and does not imply official Redragon firmware or RGB integration.

- G502 HERO product views (assets/g502-hero-top.png and assets/g502-hero-side.png):
  unmodified official Logitech product renders, retrieved 2026-11-04.
  Copyright Logitech; product names and logos identify the depicted hardware.
  No official affiliation is implied. These images are not MIT licensed.
  Product page: https://www.logitechg.com/en-us/shop/p/g502-hero-gaming-mouse
  Top: https://resource.logitechg.com/w_1200,c_limit,f_png/content/dam/gaming/en/non-braid/hyjal-g502-hero/2025/g502-hero-mouse-top-angle-gallery-1.png
  Side: https://resource.logitechg.com/w_1200,c_limit,f_png/content/dam/gaming/en/non-braid/hyjal-g502-hero/2025/g502-hero-mouse-profile-left-angle-gallery-2.png
