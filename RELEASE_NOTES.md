LogiGian64 0.2.3 para Windows 10/11 x64.

- **DPI físico del G502 HERO corregido**: comunicación HID++ 0x2201, rango y pasos leídos del sensor, escritura del valor seleccionado y lectura de confirmación. Se muestra el valor real; no se informa de éxito si el ratón no confirma.
- En Sensibilidad, pulsa **Activar control y aplicar DPI**. Con el control activo, arrastrar o seleccionar un punto aplica su DPI al sensor. Al salir o desconectar se restaura el DPI anterior; no se escribe la memoria integrada. Otros modelos conservan niveles de referencia.
- **Asignación de macros mejorada**: una biblioteca vacía abre la creación de macro; al guardar sus acciones se retoma la asignación. El G502 conecta el control directo antes de pedir identificar el botón físico. Pulsa y suelta el botón y guarda la asignación.
- Las macros de G HUB no se importan automáticamente. Si G HUB está abierto se solicita confirmación para cerrarlo antes de tomar el control.
- La X mantiene el programa y las macros en la bandeja. Para cerrar completamente, usa Salir desde su icono.
- Se conserva el editor de macros, los perfiles y la configuración de inicio con Windows.

Validación: 53 pruebas automatizadas aprobadas. En el G502 físico se leyó 3200 DPI, se aplicó 1450 DPI y se confirmó por lectura; después se confirmó la restauración a 3200 y al modo original. La captura física recibió una pulsación y su liberación; queda pendiente verificar específicamente G4/G5 y la reproducción completa de una macro con el usuario.

Descarga **LogiGian64-Setup.exe** para instalar o el ZIP portable para abrir sin instalar. No requiere Python. Instalador sin firma digital; Windows puede mostrar un aviso de editor desconocido. Código y licencias incluidos. Consulta SHA256SUMS.txt para verificar las descargas.
