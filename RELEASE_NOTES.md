LogiGian64 0.2.6 — Detección de teclados físicos e identificación de modelos.

- Corregida la tarjeta adicional «Teclado C232»: la interfaz virtual instalada por G HUB se reconoce por su árbol PnP y ya no se cuenta como un segundo teclado físico. El controlador permanece instalado y disponible para su software.
- Se mantienen agrupadas las interfaces de una misma unidad y separadas las de unidades distintas, sin cambiar sus IDs de perfiles o asignaciones.
- Nuevo botón **Identificar modelo** al configurar un periférico: fabricante y modelo guardados localmente para esa unidad. Permite identificar el Redragon KUMARA K552RGB-1 aunque sus descriptores genéricos indiquen USB DEVICE/SONiX. No se atribuye ese modelo a todos los teclados con el mismo VID/PID.
- Los nombres genéricos muestran el tipo y VID/PID. El diagnóstico conserva las interfaces virtuales excluidas en una lista separada.
- Se conservan la protección del clic izquierdo/derecho, las macros, el DPI y RGB del G502 y el inicio en bandeja.

69 pruebas automatizadas aprobadas. Comprobación en Windows: un G502 físico y un teclado físico, cada uno con sus dos interfaces agrupadas. El modelo Redragon fue confirmado por el usuario y asociado localmente a su unidad. No se incluye número de serie ni identificación personal en los paquetes.

Windows 10/11 x64. Antes de instalar, elige Salir en la bandeja de la versión anterior. Sin Python. Instalador sin firma digital. Código, licencias y SHA256SUMS.txt incluidos.
