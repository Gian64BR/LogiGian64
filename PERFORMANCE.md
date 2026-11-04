# Revisión de rendimiento — 3 de noviembre de 2026

Cambios aplicados a la versión actual de `LogiGian64-publish`, a la que apunta
el acceso directo `LogiGian64 - Pruebas.lnk`.

## Cambios

- Raw Input reutiliza un búfer por hilo y lee los reportes normales en una sola
  llamada a Windows. Mantiene el crecimiento controlado para paquetes grandes,
  el filtrado de entradas sintéticas y los identificadores de dispositivo de 64 bits.
  Los movimientos sin botones ni rueda salen antes de recorrer las acciones.
- El editor cancela la actualización pendiente cuando ya reconstruyó la línea de
  tiempo. Retira los elementos desde el final, evitando desplazar la lista entera
  en cada eliminación. No cambia los pasos ni sus retardos.
- La vista RGB reutiliza la imagen redimensionada entre cuadros; la invalida al
  cambiar de imagen o tamaño. Conserva los efectos y su frecuencia de animación.
- Las secuencias sin acciones en «Durante pulsación» esperan una señal de
  liberación o parada, en lugar de despertarse cada 10 ms.

## Mediciones

Comparación con el código de HEAD anterior a estos cambios, en este equipo.
Mediana de cinco lotes; Qt offscreen, con fuentes Segoe UI. La entrada usa
transporte simulado: estas cifras no equivalen al consumo total de Windows.

| Operación | Antes | Después | Reducción de tiempo |
|---|---:|---:|---:|
| Procesar un reporte de movimiento | 4,022 µs | 2,793 µs | 31 % |
| Actualizar editor de 200 pasos y procesar eventos | 250,28 ms | 153,33 ms | 39 % |
| Cuadro de vista RGB de 600 × 500, imagen de prueba de 1600 × 1200 | 0,870 ms | 0,303 ms | 65 % |

En 100.000 reportes simulados, las llamadas de lectura bajaron de 200.000 a
100.000. Inicio y asignaciones conservaron imágenes idénticas píxel por píxel.
La prueba RGB a tiempo fijo también conservó los mismos píxeles.
Mediciones y capturas: `qa/performance/results.json` y `qa/performance/*.png`;
script local: `qa/performance_review.py`.

## Verificación y entrega

- `python -m unittest discover -s tests -q`: 90 pruebas aprobadas, incluidas
  lectura normal y ampliada, clics, rueda, teclado, entrada sintética, caché RGB,
  actualización del editor y liberación/parada de secuencias sin bucle.
- `git diff --check`: sin errores de espacios.
- Compilación PyInstaller completada en `dist/optimized/LogiGian64.exe`.
- El ejecutable compilado inició con datos de prueba, generó las tres capturas
  solicitadas y salió con código 0.

No se alteraron perfiles personales, imágenes, diseños, instaladores publicados
ni protocolos de control del hardware. Se eliminó trabajo redundante de las rutas
frecuentes; no se borraron archivos antiguos de otras carpetas porque no se ha
demostrado que sean prescindibles. La copia anterior de `NexusHub` conserva su código.

Para usar los cambios, cerrar la instancia anterior y abrir el ejecutable de
`dist/optimized`, o volver a abrir el acceso directo de pruebas que ejecuta el
código fuente actualizado. La instalación existente no se sustituye automáticamente.
No se midió CPU global de Windows ni se realizó una sesión física prolongada con
macros y juegos; las mejoras anteriores se limitan a las operaciones verificadas.
