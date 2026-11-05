LogiGian64 0.2.14 — Reconexión, cierre y sensibilidad por perfil.

- Recuperación automática de los botones G al desenchufar y volver a conectar el G502 HERO.
- Los errores tardíos de una conexión USB anterior no desactivan la conexión nueva.
- El DPI seleccionado, los niveles y la velocidad del puntero de Windows quedan guardados en cada perfil y se vuelven a aplicar al iniciar o cambiar de perfil.
- Se conservan las preferencias anteriores; la sensibilidad también se incluye al duplicar, exportar o importar perfiles.
- Cambiar el modo del mouse ya no deja una sensibilidad distinta de la configurada. Al salir se restaura el estado anterior del sensor y al abrir se recupera el perfil activo.
- Salir desde la bandeja finaliza la aplicación con la ventana abierta u oculta. Un transporte USB desconectado o una restauración fallida ya no bloquean indefinidamente el cierre; se conserva un diagnóstico local cuando corresponde.
- Se mantienen las macros, las imágenes y el diseño existentes.

111 pruebas automatizadas aprobadas. Incluyen reconexión simulada, conservación de sensibilidad al reabrir, separación entre perfiles, mensajes tardíos y cierre real de procesos de prueba. La suite usa transporte HID simulado; no sustituye la comprobación física de todos los botones o firmwares.

Windows 10/11 x64. Incluye instalador, ZIP portable, código fuente, licencias y SHA256SUMS.txt. Cierra la versión anterior desde la bandeja antes de instalar. Se conservan los perfiles existentes. Instalador sin firma digital.
