# Verificación de LogiGian64 0.2

Fecha local: 2 de noviembre de 2026. Windows x64.

## Ejecutado

- 53 pruebas automatizadas aprobadas: comienzo al pulsar, parada al soltar,
  interrupción de esperas de 60 s, alternancia, pulsaciones rápidas, liberaciones
  de otros botones, tres fases de secuencia y limpieza de entradas pendientes.
- Persistencia, importación inválida y recuperación de bibliotecas dañadas.
- Integración de editor con activador por dispositivo. Las pruebas de reproducción
  usan emisores controlados y no envían entrada al escritorio.
- Adaptador G502 con transporte simulado: captura/restauración del modo y mapa,
  inicio fallido, rechazo de un agente G HUB concurrente y conservación de la
  propiedad de una restauración fallida para poder reintentarla.
- Revisión de capturas de la interfaz negra, asignación sobre el periférico,
  imágenes frontal/lateral, iconos vectoriales y secuencia en varias filas.
- Arrastre independiente de teclas y retardos, edición y guardado de milisegundos,
  ajuste de filas al ancho, desplazamiento vertical e inserción entre filas.
- Registro de inicio con Windows probado con un registro simulado; eliminación
  idempotente y comillas en rutas con espacios. La instalación completa y el
  inicio de sesión de Windows no forman parte de estas pruebas automatizadas.
- Espacio, Enter y Escape durante grabación no activan la navegación de Qt.

## Comprobaciones en hardware real (sin modificar su configuración)

G502 HERO 046D:C08B, conectado al equipo:

- Enumeración HID y Raw Input; agrupación de sus interfaces por Container ID.
- Consulta HID++ Root: 0x8110 localizado en índice 0x0D y 0x8100 en 0x0C.
- GetButtonCount: 11 botones.
- GetMode: modo host (2) en el momento de la consulta.
- GetButtonMapping: lectura del mapa vigente.

Las consultas de índice, número de botones, modo y mapa son lecturas de protocolo.
No se activó un mapa de prueba ni se modificaron las macros del usuario en G HUB.

## Pendiente de validación física

No se afirma haber comprobado la asignación, supresión y reproducción completa
con pulsaciones físicas del usuario, ni la restauración real de escrituras de
mapa en el G502. El adaptador implementa esos flujos, pero la prueba de transporte
simulado no demuestra su funcionamiento físico. La calibración del botón en la
aplicación permite al usuario comprobarlo al asignar.

No se probaron juegos, anticheat, todos los firmwares ni otros modelos HID++.
Los otros fabricantes utilizan por ahora el modo genérico con acción original.

## Fuentes técnicas de protocolo y análisis

- Archivos locales de G HUB: `g502_hero/metadata.json` (objetivos G1–G11),
  `default_configurations.json` (11 entradas lógicas), bundle UI (tipos de macro).
- HIDAPI: https://github.com/libusb/hidapi
- Referencia de interfaz: https://github.com/cvuchener/hidpp/tree/master/src/libhidpp/hidpp20
- Dispositivo y peculiaridad: https://github.com/libratbag/libratbag/blob/master/data/devices/logitech-g502-hero.device
- Bitmaps de botones: https://github.com/libratbag/libratbag/issues/1831

El código del adaptador es una implementación propia, no una copia del código
propietario de G HUB. No se implementan operaciones de flash o DFU.

## Actualización 0.2.2

- Cierre con X conserva la bandeja, permite restaurar la ventana y no detiene el
  reproductor. Salir desde la bandeja ejecuta la limpieza de entradas.
- Niveles de referencia: arrastre con eventos Qt, ajuste por teclado, límites,
  edición manual, guardado por dispositivo, restablecimiento y datos inválidos.
- Modificar niveles no llama al ajuste del puntero de Windows. Aplicar a Windows
  sí envía el valor elegido (verificado con un emisor simulado).
- Revisión visual a 1300x900 y 1920x1032. No se declara control físico del DPI.

## Corrección 0.2.3 — G502 HERO físico

- Se consultó 0x2201: 1 sensor, 100–25600 DPI, paso 50, valor actual 3200.
- Se inició control host temporal, se aplicó 1450 DPI y se confirmó por lectura.
- Se cerró la sesión: lectura posterior confirmó 3200 DPI y modo original 1.
- Captura de 20 s recibió pulsación/liberación del índice físico 1. No demuestra
  todavía G4/G5 ni reproducción completa de macros con pulsaciones del usuario.
- Pruebas simuladas: rechazo de valores incompatibles, lectura que no confirma
  una escritura, restauración del DPI y secuencia de conexión antes de asignar.
- Protocolo consultado: https://github.com/libratbag/libratbag/blob/master/src/hidpp20.c
  (funciones de la característica 0x2201). Implementación Python propia.
