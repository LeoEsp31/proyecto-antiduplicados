# 🛑 Detector de Descargas Duplicadas

Una extensión de navegador acoplada a un script nativo en Python que intercepta descargas, escanea el disco duro en milisegundos y previene la duplicación de archivos locales.

## 🚀 El Problema que Resuelve
Los navegadores web, por cuestiones de seguridad, no verifican si un archivo ya existe fuera de su carpeta predeterminada. Esto genera descargas redundantes (ej. `documento(1).pdf`). Este proyecto soluciona esa fricción automatizando la búsqueda local antes de que el navegador inicie la descarga, ahorrando espacio y tiempo.

## 🧠 Arquitectura y Flujo de Datos
El proyecto utiliza **Native Messaging API** para comunicar un entorno aislado (el navegador) con el sistema operativo.

1. **Frontend (Extensión):** Intercepta el evento de descarga (`onDeterminingFilename`), pausa el proceso y envía el nombre del archivo en formato JSON a través del puerto nativo.
2. **Backend (Python Host):** Un script que corre en segundo plano en Windows, recibe el mensaje por `stdin`, decodifica la longitud de los bytes y busca el archivo en la carpeta del usuario con `os.scandir`:
   * Revisa primero Descargas, Escritorio, Documentos y OneDrive, y después el resto.
   * Saltea carpetas ocultas, de sistema y de programas (`AppData`, `node_modules`, etc.).
   * Si una carpeta no tiene permisos, la saltea y sigue buscando.
   * Compara nombres sin distinguir mayúsculas, y los corchetes u otros símbolos no afectan la búsqueda.
   * Corta a los 8 segundos para no frenar la descarga.
3. **Resolución:** Si el archivo existe, Python devuelve la ruta absoluta por `stdout`. La extensión cancela la descarga nativa y lanza una notificación. Python abre el Explorador con el archivo seleccionado; **si la carpeta ya está abierta en una ventana, no abre otra**: solo selecciona el archivo en la ventana existente.
4. **Tolerancia a fallos:** Si Python falla, se cierra o no responde a tiempo, la descarga sigue normal.

## 🛠️ Tecnologías Utilizadas
* **JavaScript (ES6):** Service Workers, Chrome Extensions API (Manifest V3).
* **Python 3:** Manejo de I/O a nivel de bytes (`struct`, `sys`), llamadas al SO (`subprocess`), File System (`os.scandir`).
* **PowerShell + COM (`Shell.Application`):** Detección de ventanas del Explorador ya abiertas.
* **Windows Registry:** Integración de permisos para Native Messaging Hosts.

## ⚙️ Instalación y Uso (Modo Desarrollo)

### 1. Configurar el Host Nativo (Python)
1. Clonar el repositorio.
2. Entrar a la carpeta `host-nativo`.
3. Editar `host_manifest.json` y reemplazar el campo `allowed_origins` con el ID de la extensión.
4. Ejecutar `instalar.bat` para añadir las claves necesarias al Registro de Windows.

### 2. Instalar la Extensión
1. Abrir Chrome/Edge y navegar a `chrome://extensions/`.
2. Activar el "Modo de desarrollador".
3. Clic en "Cargar descomprimida" y seleccionar la carpeta `extension`.

## 👨‍💻 Autor
**Leandro Espinosa**
[Link a tu LinkedIn] | [Link a tu Portfolio/GitHub]