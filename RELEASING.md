# Una versión, una Release para Windows y Linux

1. Cambiar la versión con `python tools/set-version.py 0.3.2`. El archivo `VERSION`,
   los módulos de Windows/Linux y los metadatos del ejecutable quedan sincronizados.
   El instalador Windows y los empaquetadores leen esa versión automáticamente.
2. Escribir una descripción común en `RELEASE_NOTES.md`, indicando los cambios y
   las limitaciones de cada plataforma. No crear una Release independiente para Linux.
3. En Windows: ejecutar `build.ps1`, `python package_release.py` y compilar
   `installer.iss` con Inno Setup. No reutilizar un ejecutable de una versión anterior.
4. En Ubuntu 24.04 amd64: desde `linux/`, ejecutar las pruebas y
   `PYTHON=/ruta/al/python bash tools/build-linux.sh`. Seguir `linux/README-LINUX.md`
   para instalar las dependencias. No reutilizar un ejecutable Linux anterior.
5. Ejecutar `python tools/prepare-release.py` en la raíz del repositorio. Este paso
   exige los paquetes de ambas plataformas, verifica su versión y prepara una carpeta
   conjunta con instaladores, fuentes, manifiesto y un solo `SHA256SUMS.txt`.
6. Guardar el código en Git, subir una sola etiqueta `vVERSION` y crear una sola
   Release titulada `LogiGian64 VERSION — Windows y Linux`, usando la descripción
   común y todos los archivos de `dist/release-VERSION/`.
7. Verificar los archivos y sus sumas remotas antes de publicar. Mantener una sola
   entrada principal; no dividir la misma actualización en Releases por plataforma.

Linux conserva su estado de prueba dentro de la descripción conjunta. El `.deb`
actual requiere Ubuntu 24.04/Mint 22 amd64 o compatibilidad equivalente. Windows
conserva su instalador x64. macOS no está implementado.
