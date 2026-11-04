LogiGian64 0.2.11 — Optimización de rendimiento.

- Lectura de entrada del mouse y teclado con memoria reutilizable y menos llamadas a Windows.
- Eliminación de actualizaciones duplicadas en la línea de tiempo del editor.
- Reutilización de la imagen redimensionada en la vista RGB, conservando sus animaciones.
- Las secuencias sin acciones durante la pulsación esperan sin despertarse cada 10 ms.
- Se mantienen el diseño, las funciones, las imágenes y los perfiles existentes.

90 pruebas automatizadas aprobadas. Comparación de operaciones concretas: 31 % menos tiempo al procesar movimiento simulado, 39 % menos al actualizar un editor de 200 pasos y 65 % menos por cuadro RGB de prueba. No representan una medición del consumo total de Windows. Informe incluido en PERFORMANCE.md.

Windows 10/11 x64. Cierra la versión anterior desde la bandeja antes de instalar. El instalador actualiza la aplicación conservando los perfiles. Incluye ZIP portable, código fuente, licencias y SHA256SUMS.txt. Instalador sin firma digital.
