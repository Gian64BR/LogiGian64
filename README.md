# LogiGian64 0.2.4 — Macros y asignaciones

Aplicación independiente para Windows 10/11 x64, con un espacio de trabajo negro,
panel lateral y asignación de macros sobre la imagen del periférico.

## Abrir

Descarga **LogiGian64-Setup.exe** desde [Releases](https://github.com/Gian64BR/LogiGian64/releases/latest) y sigue el asistente. Se instala para tu usuario, incluye desinstalador y permite crear un acceso directo.

También puedes descargar el ZIP portable, extraerlo y ejecutar `LogiGian64.exe`.
No requiere instalar Python en el equipo de destino.

Versión de prueba para Windows 10/11 x64. El instalador no tiene firma digital;
Windows puede mostrar un aviso de editor desconocido. Comprueba los archivos con
`Get-FileHash .\LogiGian64-Setup.exe -Algorithm SHA256` y el archivo SHA256SUMS.txt de la Release.

## Crear y asignar una macro

1. Selecciona tu periférico en **Dispositivos**.
2. Pulsa **Crear nueva macro**, escribe su nombre y elige el modo.
3. Añade teclas, botones, rueda, retardos, texto/emojis, aplicaciones o acciones
   multimedia con **+**. La grabación se añade a la sección actual; F8 la termina.
4. Puedes elegir retardo estándar de 50 ms, tiempos por paso, color y mostrar u
   ocultar las liberaciones. **Editar tiempos / pasos** abre la tabla detallada.
5. Guarda, vuelve a Asignaciones y arrastra la macro al objetivo del periférico.
6. Pulsa y suelta físicamente el botón o tecla solicitado para identificarlo y
   guarda la asignación. No se adivina el botón a partir de acciones de otro software.

## Modos de ejecución

| Modo | Al pulsar | Al soltar |
|---|---|---|
| Sin repetición | Ejecuta una vez inmediatamente | Permite terminar esa ejecución |
| Repetir durante pulsación | Inicia el bucle | Lo interrumpe, incluidas las esperas, y libera entradas pendientes |
| Alternante | Primera pulsación inicia; siguiente pulsación detiene | No detiene el bucle |
| Secuencia | Ejecuta Al pulsar y después repite Durante pulsación | Interrumpe la fase central y ejecuta Al soltar |

En Secuencia se editan las tres secciones por separado. Se puede, por ejemplo,
pulsar Ctrl en la primera sección, repetir clics en la segunda y soltar Ctrl en
la tercera. Si se suelta rápidamente, la parte Al pulsar también se puede
interrumpir; solo se liberan salidas que realmente llegaron a pulsarse.

**Ctrl+Alt+F12** detiene las macros, pausa asignaciones y desconecta/restaura el
control directo. F9 ya se puede utilizar como acción o activador.
**Prueba única en 3 s** reproduce un pase finito; para comprobar el modo mientras
se mantiene pulsado se debe usar el activador físico asignado.

## G502 HERO: botones físicos G1–G11

El adaptador directo está limitado a **Logitech G502 HERO 046D:C08B**. Consulta
HID++ en el propio dispositivo; no depende de la base de datos de G HUB.

Pulsa **Activar botones G**. Si G HUB está abierto, se muestra una confirmación
para cerrar su interfaz, bandeja y agente. Guarda antes las ediciones pendientes
en G HUB. No se modifica su configuración ni se detiene el actualizador.

Nexus guarda el modo y mapa actuales, inicia el canal de botones físicos y reserva
los botones asignados en un mapa temporal del modo host. La calibración confirma
el control físico al pulsarlo. Al quitar asignaciones, desconectar el control o
salir se restaura la configuración anterior. No se escribe flash ni memoria de
perfiles integrados. Si G HUB reaparece, el adaptador se detiene para evitar
controladores simultáneos.

El adaptador requiere validación física de extremo a extremo con tus botones;
la detección de 11 botones y las consultas de modo/mapa se verificaron en este
G502, y las transiciones/restauraciones se probaron con transporte controlado.
No se afirma que las escrituras de mapa y todos los botones se hayan probado
físicamente todavía. Si una restauración falla, se conserva la sesión para
reintentar; no se informa de restauración exitosa sin confirmación.

## Otros periféricos y límites

- Windows Raw Input permite detectar teclados y ratones sin depender de la marca.
- En dispositivos genéricos, las macros responden al activador, pero conservan
  también su acción original. La supresión física requiere un adaptador del modelo.
- Los botones que no se exponen a Windows necesitan un adaptador como el del G502.
- DPI físico disponible para G502 HERO 046D:C08B con control directo activo y
  confirmación de lectura. RGB, polling y escritura en memoria integrada no
  están implementados. Otros modelos mantienen niveles de referencia.
- Los perfiles se seleccionan manualmente. Nexus debe permanecer abierto o en la
  bandeja. Windows puede bloquear SendInput hacia aplicaciones con más privilegios.
- Los juegos que ignoren entrada sintética no están verificados.

Datos: `%LOCALAPPDATA%\NexusHub\profiles.json`. El formato 0.2 conserva una copia
v1 antes de guardar el nuevo esquema. La biblioteca permite importar/exportar JSON.
No se capturan ni guardan teclas fuera del modo de grabación activado por el usuario.

## Imágenes

En un equipo con G HUB instalado, Nexus puede leer sus imágenes locales de
referencia para mostrar el G502 frontal/lateral. Esas imágenes siguen siendo
propiedad de su titular y **no se incluyen** en el ejecutable ni en el código
fuente distribuido. Sin ellas se dibuja una ilustración propia como alternativa.

## Desarrollo

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
python -m unittest discover -s tests -v
.\build.ps1
```

Código original MIT. Dependencias: Qt/PySide6, Python y HIDAPI. El motor de modos
está en `nexus/macro_engine.py`; los perfiles en `nexus/core.py`; el adaptador
HID++ en `nexus/g502.py`; el espacio de trabajo en `nexus/studio.py` y
`nexus/studio_widgets.py`. Consulta `VALIDATION.md` y `THIRD_PARTY_NOTICES.md`.

## Menú de cada botón

Pulsa el círculo o su nombre para abrir **Usar predeterminada**, **Desactivar**
o **Asignar macro**. Desactivar quita inmediatamente la macro de ese botón y
lo deja únicamente con el círculo, sin línea ni texto; se guarda por perfil.
No requiere activar Botones G ni calibración. La acción nativa de un ratón HID
genérico continúa disponible. En el G502 conectado directamente, los controles
ya identificados también se suprimen en el mapa temporal mientras Nexus está activo.

Usar predeterminada elimina la personalización de Nexus y devuelve el botón al
mapa original capturado al conectar; no restablece perfiles de fábrica de G HUB.

## KNUP KP-V84

El mouse identificado por el usuario como KNUP KP-V84 (USB 30FA:0400) tiene
ilustraciones propias superior y lateral basadas en sus referencias. Se incluyen
en el ejecutable y los paquetes. VISTA 1 muestra los clics principal, secundario
y central; VISTA 2 muestra Atrás y Adelante. No se declara soporte de control
DPI, iluminación o supresión física para este mouse HID genérico.

## Grabación y guardado

Guardar confirma la macro y vuelve a Asignaciones. El retardo estándar aplica
el valor visible (50 ms inicialmente) a cada acción y lo muestra en la tabla;
las pausas explícitas conservan su duración. Desmarcarlo permite editar tiempos
individuales. Se graban combinaciones de teclado, clic izquierdo/derecho,
central, laterales y rueda, también dentro de Nexus. El control de inicio/fin
de grabación queda excluido; F8 finaliza y Ctrl+Alt+F12 detiene las macros.

Para ratones HID genéricos, Central y Lateral 4/5 pueden asignarse directamente
a los botones estándar middle/x1/x2 sin calibración. Nexus recibe su entrada
por dispositivo; no suprime la acción original Atrás/Adelante de estos ratones.

## Biblioteca y navegación

Clic derecho sobre una macro abre Editar, Renombrar y Eliminar. La lista muestra
sus nombres sin prefijo M. Los iconos de navegación lateral muestran fondo celeste
solamente en la sección seleccionada.

## Mantener pulsado

Quinta opción al crear una macro. Graba o añade las teclas y clics que quieres
mantener (pueden ser varios a la vez). La primera pulsación del activador envía
una sola pulsación de cada salida y las deja mantenidas, incluso al soltar el
activador. La siguiente pulsación las libera. No hay bucle ni temporizador; se
ignoran retardos y liberaciones grabadas. Admite teclas y botones del mouse.
Detener, pausar asignaciones, cerrar Nexus o sustituir la macro libera las
salidas pendientes. La prueba manual sigue siendo finita.


## Configuración e inicio con Windows

El engranaje inferior izquierdo permite activar o desactivar **Iniciar con Windows**.
Las instalaciones nuevas lo activan por defecto para el usuario actual; las
actualizaciones conservan la elección anterior. La desinstalación elimina la entrada.
Por defecto aparece la ventana al iniciar sesión. Puedes elegir **Al iniciar con
Windows, abrir en la bandeja**. Abrir manualmente sigue mostrando la ventana.
El menú también permite pausar asignaciones, detener macros y restaurar el control,
abrir la carpeta de perfiles y minimizar a la bandeja.

## Sensibilidad y bandeja (0.2.4)

La pantalla Sensibilidad permite arrastrar cinco niveles o editar sus valores.
En el **G502 HERO 046D:C08B**, pulsa **Activar control y aplicar DPI**. Una vez
conectado, seleccionar o mover un punto cambia el DPI físico mediante HID++
0x2201. El valor solo se informa como aplicado cuando el sensor lo confirma por
lectura. Se respetan el rango y los pasos comunicados por el dispositivo. Al
salir o desconectar el control directo se restaura el DPI anterior. No se escribe
la memoria integrada. En otros modelos los niveles siguen siendo de referencia.
La velocidad global de Windows es un control independiente.

Para asignar una macro, créala, añade o graba acciones y guarda. Si pulsas un
objetivo con la biblioteca vacía, se abre la creación de macro. Al guardar se
retoma la asignación. En el G502 se conecta el control directo antes de identificar
el botón: pulsa y suelta el botón físico y guarda la asignación. Si G HUB está
abierto, el programa pide confirmación antes de cerrarlo. Las macros de G HUB
no se importan automáticamente.

La X oculta la ventana sin detener las macros. Doble clic en el icono de la
bandeja vuelve a abrirla. Para terminar el programa, elige **Salir** en su menú.

## Protección permanente de los clics principales (0.2.4)

Clic izquierdo y derecho (G1/G2) están protegidos. No se pueden asignar a macros
ni desactivar, tampoco al calibrar otro objetivo. Los perfiles antiguos y los
importados omiten sus asignaciones o desactivaciones sin borrar las macros.
El controlador del G502 mantiene sus entradas nativas 1 y 2, incluso si recibe
una solicitud antigua para suprimirlas. Los demás botones continúan disponibles.
