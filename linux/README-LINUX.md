# LogiGian64 Linux — 0.3.1 (versión de prueba)

La edición Windows no se modifica. Esta edición conserva la interfaz, los perfiles,
el editor y el motor de macros; reemplaza la entrada nativa por evdev/uinput y adapta
la identificación HID++ del G502 HERO a Linux.

## Instalar el paquete

Paquete amd64 compilado en Ubuntu 24.04: Ubuntu 24.04, Linux Mint 22 y sistemas
compatibles con glibc 2.39 o posterior. No sirve para ARM ni para Debian 12.

```sh
sudo apt install ./LogiGian64-0.3.1-amd64.deb
sudo bash /opt/logigian64-linux/tools/enable-device-access.sh "$USER"
```

Cierra la sesión y vuelve a entrar. Abre **LogiGian64 Linux** desde el menú.
Los permisos permiten a tu usuario leer teclados/mouses y generar entrada mediante
uinput; se conceden mediante un grupo dedicado, sin permisos de escritura para todos.
La interfaz se ejecuta como usuario normal. No ejecutes la interfaz con sudo.

## Debian 12 / Ubuntu 22.04 / Mint 21 y otras versiones

Usa el archivo source.tar.gz para instalar con el Python del sistema (3.10 o posterior):

```sh
sudo apt install python3-venv python3-dev gcc linux-libc-dev libudev1 libegl1 libopengl0 libxkbcommon0 libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libdbus-1-3 libglib2.0-0 libfontconfig1 libgl1 udev
tar -xzf LogiGian64-0.3.1-Linux-source.tar.gz
cd LogiGian64-linux
bash install.sh
sudo bash "${XDG_DATA_HOME:-$HOME/.local/share}/logigian64-app/tools/enable-device-access.sh" "$USER"
```

Requiere internet para descargar las dependencias. La instalación usa un entorno
Python privado; no modifica el Python del sistema. Estas distribuciones requieren
validación en un escritorio real; la compilación y las pruebas automatizadas se
realizan en Ubuntu 24.04 bajo WSL.

## Alcance de esta primera versión

- Lectura de teclas, botones y rueda; macros de teclas, texto, rueda y aplicaciones.
  Los botones conservan también su acción física; no se bloquea el dispositivo.
- uinput funciona a nivel del sistema: las macros pueden utilizarse en X11 y Wayland
  si el sistema permite los dispositivos. Los atajos reservados dependen del escritorio.
- Las acciones de texto admiten ASCII con distribución US. Texto con acentos/Unicode
  y escritura automática en otras distribuciones todavía necesitan adaptación.
- DPI, frecuencia y RGB del G502 HERO usan HID++ y requieren acceso a hidraw.
  La validación física en Linux con el mouse conectado sigue pendiente. Cierra
  Solaar, ratbagd u OpenRGB si están controlando el mismo dispositivo.
- La velocidad/aceleración global del puntero se configura en el escritorio Linux.
- Otros teclados y mouses mantienen la detección y las imágenes del catálogo; no
  se promete control RGB de hardware sin un protocolo compatible.
- En GNOME sin bandeja, el inicio automático muestra la ventana minimizada.
- Perfiles en `${XDG_DATA_HOME:-$HOME/.local/share}/logigian64`. Puedes importar
  perfiles, pero debes reasignar los dispositivos y las rutas de aplicaciones Linux.

Diagnóstico sin tomar control del hardware: `logigian64-linux --diagnose`.
Los archivos de registro están junto a los perfiles.

## Compilar desde fuentes

En Ubuntu 24.04 amd64 con las dependencias de sistema indicadas arriba:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt 'pyinstaller>=6.16,<7'
PYTHON=.venv/bin/python bash tools/build-linux.sh
```

El instalador y el archivo de fuentes se generan en `dist/`. El ejecutable se
compila de forma nativa en Linux. No se pueden usar los binarios de Windows.

## Desinstalar

Cierra el programa desde Salir. El paquete también detiene su propio ejecutable
antes de quitarlo. Los perfiles personales se conservan.

```sh
sudo bash /opt/logigian64-linux/tools/disable-device-access.sh
sudo apt remove logigian64-linux
```

En una instalación desde fuentes, cierra la aplicación, retira los permisos usando
el script tools/disable-device-access.sh de esa copia y elimina la carpeta
logigian64-app, ~/.local/bin/logigian64-linux y la entrada de menú
~/.local/share/applications/logigian64-linux.desktop. Desactiva el inicio automático
desde Ajustes antes de desinstalar. No borres la carpeta de perfiles si los quieres conservar.
