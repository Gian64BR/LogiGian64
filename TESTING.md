# Pruebas sin recompilar

Para ejecutar el código editable, instalar `requirements.txt` con Python 3.11
y abrir `python main.py` desde la carpeta del proyecto. Usa los mismos perfiles de `%LOCALAPPDATA%\NexusHub` que el ejecutable
instalado. Elegir **Salir** en el menú del icono de la bandeja antes de abrir otra
instancia. Después de cada modificación del código basta salir desde la bandeja
y volver a ejecutar `python main.py`. La X oculta la ventana y mantiene las macros
activas; doble clic en el icono de la bandeja vuelve a mostrarla.

El ejecutable instalado y el instalador se conservan hasta que el usuario pida
compilarlos y actualizarlos.

En el editor, desmarcar **Usar retardos estándar** muestra los tiempos separados.
Arrastrar un bloque rojo mueve la acción; arrastrar el número con `ms` mueve solo
ese retardo. Doble clic en el número permite editarlo. Las flechas debajo/encima
indican pulsar/soltar. `+` abre las opciones de colores para añadir acciones.

La grabación usa Raw Input; el filtro de Qt impide que las teclas grabadas activen
botones o navegación por foco. F8 sigue finalizando la grabación y Ctrl+Alt+F12
mantiene la parada de emergencia.
