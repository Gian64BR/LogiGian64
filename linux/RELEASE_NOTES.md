# LogiGian64 0.3.0-linux.1 — primera versión Linux de prueba

La interfaz, los perfiles y el editor de macros conservan el diseño de Windows.
La entrada nativa usa evdev/uinput y el control HID++ del G502 se identifica por
su dispositivo físico en Linux. Windows mantiene la versión 0.2.28.

- `.deb` amd64 para Ubuntu 24.04/Mint 22; requiere glibc 2.39 o posterior.
- Instalación desde fuentes para Debian y versiones anteriores con Python 3.10+.
- Perfiles y arranque automático mediante rutas XDG.
- Permisos mediante grupo dedicado; la interfaz no necesita ejecutarse como root.
- Inicio minimizado cuando el escritorio no ofrece bandeja; opción Salir en Ajustes.

**Instalación y permisos:** consulta README-LINUX.md dentro del archivo de fuentes,
o [la guía del repositorio](https://github.com/Gian64BR/LogiGian64/blob/main/linux/README-LINUX.md).

**Validación:** 89 pruebas automatizadas aprobadas en Ubuntu 24.04 bajo WSL;
paquete compilado abierto y cerrado, inicio automático y SIGTERM comprobados.
Prueba real uinput → evdev con F24 pulsada y liberada, sin capturar la propia entrada virtual.

**Limitaciones de esta prueba:** falta validar el G502 físico en Linux (botones,
DPI, frecuencia y RGB). El texto automático admite ASCII con distribución US;
Unicode y otras distribuciones de teclado quedan pendientes. La velocidad global
del puntero se configura en el escritorio. Debian y otras versiones requieren
pruebas en un escritorio real. No es una versión para macOS.

Se adjuntan las fuentes, las capturas del ejecutable y las sumas SHA256.
