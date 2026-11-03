LogiGian64 0.2.4 — Protección del clic izquierdo y derecho.

- **Clic izquierdo y derecho (G1/G2) protegidos**: no admiten asignación de macros ni desactivación. La interfaz los identifica como PROTEGIDOS.
- La calibración rechaza estos clics incluso si se pulsa uno mientras se asigna otro objetivo.
- Los perfiles antiguos o importados omiten asignaciones y desactivaciones que afecten a esos controles, conservando las macros y los demás botones.
- El controlador del G502 impide suprimir los índices físicos 0 y 1 y conserva sus acciones nativas en el mapa temporal y al restaurarlo. La reproducción también ignora asignaciones antiguas que intenten usarlos como activadores.
- Conserva el DPI físico del G502, las macros para los demás botones, el inicio con Windows y el cierre a la bandeja.

56 pruebas automatizadas aprobadas, incluidas las protecciones de interfaz, calibración, perfiles y paquetes del controlador. Antes de actualizar, elige Salir en la bandeja de la versión anterior. Si necesitas detener el control anterior, usa Ctrl+Alt+F12.

Instalador para Windows 10/11 x64 sin Python. Ejecutable sin firma digital. Código fuente, licencias y SHA256SUMS.txt incluidos.
