# LogiGian64 0.3.1 — Windows y Linux

Una sola versión y una sola Release para las dos plataformas. Las próximas
actualizaciones de LogiGian64 mantendrán este formato conjunto.

## Lo realizado

- **Windows:** detección separada de teclado y mouse en receptores inalámbricos
  compartidos, conservando la identidad del G502. Identificación local del Havit
  KB830WB con su imagen y teclas alineadas; el mouse del receptor aparece al detectar
  actividad real. Los teclados desconocidos utilizan la fotografía genérica indicada.
- **Linux (versión de prueba):** se conserva el diseño, los perfiles y el editor.
  Entrada nativa con evdev/uinput, identificación HID++ del G502, perfiles y arranque
  en rutas XDG, permisos por grupo y salida accesible en escritorios sin bandeja.
- **Publicaciones:** numeración compartida 0.3.1 en los dos ejecutables e instaladores,
  paquetes de ambas plataformas reunidos y un solo archivo de sumas SHA256.

## Qué descargar

| Sistema | Archivo |
|---|---|
| Windows 10/11 x64 | `LogiGian64-Setup.exe` |
| Windows portable | `LogiGian64-0.3.1-Windows-x64.zip` |
| Ubuntu 24.04 / Linux Mint 22, amd64 | `LogiGian64-0.3.1-amd64.deb` |
| Debian y otras versiones de Linux | `LogiGian64-0.3.1-Linux-source.tar.gz` |

También se incluyen las fuentes de Windows, los manifiestos de ambas plataformas
y un único `SHA256SUMS.txt`. Las fuentes completas de ambas plataformas están en
la etiqueta Git `v0.3.1`.

## Instalación de Linux y alcance

Consulta [la guía de Linux](https://github.com/Gian64BR/LogiGian64/blob/v0.3.1/linux/README-LINUX.md)
para instalar y habilitar los permisos como usuario normal. El `.deb` requiere
amd64 y glibc 2.39 o posterior; para otras versiones se ofrece la instalación desde fuentes.

Windows mantiene las funciones y el diseño probados. Linux continúa en prueba:
falta validar el G502 físico (botones, DPI, frecuencia y RGB); el texto automático
admite ASCII con distribución US, con Unicode y otras distribuciones pendientes.
La velocidad global del puntero se configura en el escritorio Linux. Debian y
otras versiones necesitan validación en un escritorio real.

Validación: 158 pruebas de Windows y 89 de Linux; apertura y cierre de paquetes,
inicio automático y liberación del bloqueo comprobados en Linux bajo Ubuntu/WSL.
La entrada virtual se comprobó mediante una pulsación y liberación F24 recibida
por el kernel, sin capturar la propia entrada virtual.

macOS queda para una actualización posterior.
