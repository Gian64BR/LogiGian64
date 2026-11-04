# Verificación de LogiGian64 0.2.11

Fecha local: 3 de noviembre de 2026. Windows x64.

- 90 pruebas automatizadas aprobadas, incluidas las regresiones de rendimiento.
- Comparación visual y de rendimiento documentada en PERFORMANCE.md.
- El ejecutable 0.2.11, los ZIP y el instalador se reconstruyen para esta Release.
- Se conserva el alcance y las limitaciones de validación física detalladas abajo.

## Historial de validación 0.2


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

## Protección de clics 0.2.4

56 pruebas aprobadas. Se verificó que los objetivos principales no permiten
asignar ni desactivar, que la calibración rechaza los índices 0/1, que los
perfiles limpian tanto slots protegidos como activadores disfrazados bajo otro
slot, y que todos los mapas enviados por el controlador conservan [1,2].

## Iluminación e inicio 0.2.5

- 63 pruebas aprobadas: captura/restauración de efectos y propietario, escritura
  volátil, conversión de parámetros, validación de valores, rechazo de una lectura
  que no confirma y conservación del control para reintentar restauraciones.
- Integración del hilo HID con el panel, persistencia por zonas y vista previa.
- Prueba física G502: 0x8070 índice 2, zonas 0 Principal y 1 Logotipo; efectos
  disponibles 0/1/10/3 con ordinales 0/1/2/3. Se aplicaron respiración roja
  2000 ms 60%, color fijo celeste 45% y ciclo 3000 ms 40% en ambas zonas.
  Lectura de parámetros y restauración completas confirmadas. No se alteraron
  botones ni DPI en esta prueba RGB directa.
- Firmware G502 declara capacidades extendidas cero, pero acepta getZoneEffect;
  se exige lectura exitosa para capturar/restaurar, sin depender de ese bit.
- Prueba de inicio real del punto de entrada en procesos aislados: --startup
  no genera eventos de mostrar ventana, incluso con preferencia antigua false;
  inicio manual sí la muestra.
- Referencias de protocolo consultadas (implementación propia):
  https://openlogi.org/hidpp/features/x8070-color-led-effects
  https://github.com/pwr-Solaar/Solaar/blob/master/lib/logitech_receiver/hidpp20.py

## Detección de teclados 0.2.6

- 69 pruebas aprobadas: recorrido PnP nativo, clasificación virtual basada en
  ascendencia, conservación de dispositivos desconocidos/USB/Bluetooth, agrupado
  de varias interfaces sin fusionar unidades distintas y asociación local de
  modelos con verificación de identidad/tipo/VID/PID. Diálogo de identificación
  probado mediante interacción controlada.
- En Windows, C232 tenía como padre LGHUBDEVICE y servicio logi_joy_vir_hid;
  el teclado real tenía ascendencia USB, VID 0C45 y PID 5004, dos interfaces
  Raw Input y descriptores genéricos USB DEVICE/SONiX.
- Después del cambio: dos periféricos físicos (G502 y Redragon confirmado por el
  usuario); no se deshabilitaron controladores ni se cambiaron IDs de perfiles.
- La identificación del modelo es local y confirmada por el usuario; los IDs
  USB genéricos no se usan como catálogo universal de ese modelo.
- Referencias: Microsoft CM_Locate_DevNodeW, CM_Get_Parent, CM_Get_Device_IDW.
  https://learn.microsoft.com/en-us/windows/win32/api/cfgmgr32/nf-cfgmgr32-cm_get_parent

## Foto y teclas de función 0.2.7

- 75 pruebas aprobadas. Foto JPEG original conservada byte por byte; la vista
  encuadra su cuerpo sin generar un archivo de imagen modificado.
- Doce objetivos F1–F12 comprobados a 1100x790 y 1920x1032; los clics de sus
  centros encuentran el objetivo correspondiente. Revisión visual de alineación
  con las teclas de la fotografía a 1300x900 y 1920x1032.
- Asignación directa, guardado por dispositivo y ejecución simulada de F1–F12,
  incluida F8 fuera de grabación y F12 sin modificadores. No se envió entrada
  al escritorio durante las pruebas del reproductor.
- Un segundo teclado no activa las macros de la primera unidad. Se rechazan
  letras/objetivos genéricos y desactivaciones del teclado. Grabación de F8 y
  emergencia Ctrl+Alt+F12 conservadas. Las acciones grabadas no se restringen.
- No hay supresión nativa de teclas; sus acciones de Windows permanecen activas.

## Desactivación, foto y nombre 0.2.8

- 79 pruebas aprobadas. Clic derecho Qt sobre el objetivo F6 desactiva y reactiva
  desde el menú; el botón lateral hace lo mismo y persiste el estado. La macro
  y sus pasos permanecen guardados.
- Se comprobó que una macro desactivada no reproduce entradas; al reactivar vuelve
  a ejecutarse. Desactivar una tecla diferente no cancela la macro en ejecución;
  desactivar su propia tecla libera las salidas mantenidas. Emisores controlados.
- Identificación recordada: cambio de puerto con una única unidad compatible;
  rechazo de reutilización si hay dos unidades, modelos ambiguos o preferencia
  de recuerdo desactivada. No se altera el ID de las asignaciones.
- Foto aportada actualizada: 1500x607, archivo conservado byte por byte; encuadre
  de cuerpo (52,78,1396,498) y mismos centros F1–F12. Revisión visual en ventana
  normal y maximizada. Nombre local confirmado Redragon K552RGB-1.

## Versión 0.2.9 — 3 de noviembre de 2026

81 pruebas aprobadas. Se reprodujo el fallo en el ejecutable instalado 0.2.8 usando LOCALAPPDATA vacío y una biblioteca de prueba separada. Se comprobó el ejecutable compilado 0.2.9 en una ventana nativa visible, también con LOCALAPPDATA vacío: tarjeta Redragon K552RGB-1 con fotografía original y panel de asignaciones con la misma fotografía y objetivos F1–F12 alineados. No se cambiaron macros del usuario ni se activó el control del hardware durante esta verificación. Los perfiles locales explícitos mantienen prioridad. El perfil incluido es un valor predeterminado para un descriptor genérico compartido, no una identificación inequívoca de cualquier teclado 0C45:5004.

## Versión 0.2.10 — 3 de noviembre de 2026

84 pruebas aprobadas, incluidas lectura RIDI_DEVICEINFO por handle, error de consulta sin inventar capacidades, objetivos para ratones genéricos de 2/3/5 botones, cambio de dispositivo y rechazo de botón lateral inexistente. El mouse físico USB 0000:3825 informa tres botones. Se verificó en ventana nativa desde el código fuente el mouse con su imagen genérica, tres objetivos y clics protegidos; el usuario aprobó el aspecto y funcionamiento local. Perfiles: comprobados selección turquesa, botones internos de renombrar/borrar y cancelación de eliminación en biblioteca de prueba separada. Los recursos y los cambios no incluyen bibliotecas personales.

El ejecutable 0.2.10 terminó su prueba aislada con código 0 y generó capturas de Dispositivos, Asignaciones y Macros. Se comprobó dentro del archivo compilado la igualdad exacta de generic-mouse.png, device-models.json y la fotografía del Redragon respecto del código fuente.
