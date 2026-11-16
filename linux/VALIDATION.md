# Linux 0.3.0-linux.1 — validación

- Ubuntu 24.04 amd64 bajo WSL, Python 3.12.
- 89 pruebas automatizadas aprobadas: perfiles, editor, modos de macro, protocolos HID++ simulados y adaptador Linux.
- Ejecutable nativo empaquetado: diagnóstico, apertura de interfaz, inicio automático, cierre por SIGTERM y eliminación del bloqueo comprobados.
- Paquete .deb extraído y probado; permisos de archivos y resolución de dependencias comprobados.
- Prueba real del kernel: F24 pulsada y liberada mediante uinput, recibida por evdev; el dispositivo virtual se excluye de la detección normal.
- Capturas del ejecutable empaquetado revisadas.
- No se probó un G502 físico conectado a Linux. DPI, frecuencia y RGB requieren validación física.
- Las acciones de texto admiten ASCII con distribución US; falta soporte Unicode y de otras distribuciones.
- Debian y versiones anteriores ofrecen instalación desde fuentes; no se validaron en un escritorio real.
- macOS no implementado.
