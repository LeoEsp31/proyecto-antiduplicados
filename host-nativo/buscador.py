import json
import logging
import os
import stat
import struct
import subprocess
import sys
import time
import unicodedata
from logging.handlers import RotatingFileHandler

# --- 0. Configuración ---

# Log rotativo: como máximo 1 MB por archivo y 2 copias viejas, así no crece para siempre.
RUTA_LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug_buscador.log')
_manejador = RotatingFileHandler(RUTA_LOG, maxBytes=1_000_000, backupCount=2, encoding='utf-8')
_manejador.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
log = logging.getLogger('buscador')
log.setLevel(logging.INFO)
log.addHandler(_manejador)

CARPETA_USUARIO = os.path.expanduser("~")

# Si la búsqueda tarda más que esto, se corta y la descarga sigue normal.
LIMITE_SEGUNDOS = 8

# Carpetas que no vale la pena recorrer: datos de programas, dependencias, cachés.
CARPETAS_IGNORADAS = {
    'appdata', 'node_modules', '__pycache__', 'venv', 'env',
    'site-packages', '$recycle.bin', 'windows', 'program files',
}

# Donde suelen estar las descargas y los documentos: se revisan primero.
CARPETAS_PRIORITARIAS = [
    'Downloads', 'Descargas',
    'OneDrive\\Escritorio', 'Desktop', 'Escritorio',
    'OneDrive\\Documentos', 'Documents', 'Documentos',
    'OneDrive',
]

# Sin esto, cada llamada a PowerShell abriría una ventana negra por un instante.
SIN_VENTANA = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


# --- 1. Comunicación con Chrome (Native Messaging) ---

def leer_mensaje():
    """Lee un mensaje de Chrome por stdin. Devuelve None si Chrome cerró la conexión."""
    raw_length = sys.stdin.buffer.read(4)
    if len(raw_length) < 4:
        return None
    message_length = struct.unpack('@I', raw_length)[0]
    message = sys.stdin.buffer.read(message_length).decode('utf-8')
    return json.loads(message)


def enviar_mensaje(mensaje_dict):
    """Manda un diccionario como JSON a Chrome por stdout."""
    mensaje_json = json.dumps(mensaje_dict).encode('utf-8')
    sys.stdout.buffer.write(struct.pack('@I', len(mensaje_json)))
    sys.stdout.buffer.write(mensaje_json)
    sys.stdout.buffer.flush()


# --- 2. Búsqueda en el disco ---

def normalizar(nombre):
    """Windows no distingue mayúsculas, y un acento puede venir escrito de dos formas."""
    return unicodedata.normalize('NFC', nombre).casefold()


def clave_ruta(ruta):
    return os.path.normcase(os.path.abspath(ruta))


def hay_que_saltear(entrada):
    """True para carpetas ocultas, de sistema, accesos directos de carpeta o sin interés."""
    nombre = entrada.name
    if nombre.startswith('.') or nombre.casefold() in CARPETAS_IGNORADAS:
        return True
    if entrada.is_symlink() or entrada.is_junction():
        return True
    try:
        atributos = entrada.stat(follow_symlinks=False).st_file_attributes
    except (OSError, AttributeError):
        return False
    return bool(atributos & (stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM))


def recorrer(raiz, objetivo, vencimiento, ya_revisadas):
    """Recorre 'raiz' buscando un archivo cuyo nombre normalizado sea 'objetivo'.

    Un error de permisos en una carpeta solo saltea esa carpeta, no corta la búsqueda.
    Compara nombres directamente (no usa comodines), así que '[', ']' o '*' no molestan.
    """
    pendientes = [raiz]
    while pendientes:
        if time.monotonic() > vencimiento:
            raise TimeoutError
        carpeta = pendientes.pop()
        if clave_ruta(carpeta) in ya_revisadas:
            continue
        try:
            with os.scandir(carpeta) as entradas:
                for entrada in entradas:
                    try:
                        if entrada.is_dir(follow_symlinks=False):
                            if not hay_que_saltear(entrada):
                                pendientes.append(entrada.path)
                        elif normalizar(entrada.name) == objetivo:
                            return entrada.path
                    except OSError:
                        continue
        except OSError:
            continue  # sin permiso, carpeta borrada mientras buscábamos, etc.
    return None


def buscar_archivo(nombre_archivo, carpeta_base=CARPETA_USUARIO, limite=LIMITE_SEGUNDOS):
    """Busca primero en las carpetas habituales y después en el resto.

    Devuelve (ruta o None, se_agoto_el_tiempo).
    """
    objetivo = normalizar(nombre_archivo)
    vencimiento = time.monotonic() + limite
    ya_revisadas = set()
    raices = [os.path.join(carpeta_base, c) for c in CARPETAS_PRIORITARIAS]
    raices.append(carpeta_base)
    try:
        for raiz in raices:
            if not os.path.isdir(raiz):
                continue
            ruta = recorrer(raiz, objetivo, vencimiento, ya_revisadas)
            if ruta:
                return ruta, False
            ya_revisadas.add(clave_ruta(raiz))
    except TimeoutError:
        return None, True
    return None, False


# --- 3. Abrir la carpeta (sin repetir ventanas) ---

# Recorre las ventanas abiertas del Explorador. Si alguna ya muestra la carpeta,
# selecciona el archivo ahí y responde 'ya_abierta' en vez de abrir otra ventana.
SCRIPT_VENTANAS = r'''
$carpeta = $env:DETECTOR_CARPETA.TrimEnd('\')
$nombre = $env:DETECTOR_NOMBRE
foreach ($v in (New-Object -ComObject Shell.Application).Windows()) {
    try { $p = $v.Document.Folder.Self.Path } catch { continue }
    if ($p -and $p.TrimEnd('\') -ieq $carpeta) {
        try {
            $item = $v.Document.Folder.ParseName($nombre)
            if ($item) { $v.Document.SelectItem($item, 29) }
        } catch {}
        'ya_abierta'
        exit
    }
}
'no_abierta'
'''


def carpeta_ya_abierta(ruta_archivo):
    """True si una ventana del Explorador ya muestra la carpeta de ese archivo."""
    try:
        resultado = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
             '-Command', SCRIPT_VENTANAS],
            env={**os.environ,
                 'DETECTOR_CARPETA': os.path.dirname(ruta_archivo),
                 'DETECTOR_NOMBRE': os.path.basename(ruta_archivo)},
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=5, creationflags=SIN_VENTANA,
        )
        return 'ya_abierta' in resultado.stdout
    except Exception as error:
        log.warning(f"No se pudieron revisar las ventanas abiertas: {error}")
        return False


def mostrar_en_explorador(ruta_archivo):
    """Abre la carpeta con el archivo seleccionado, salvo que ya esté abierta.

    Devuelve True si la carpeta ya estaba abierta.
    """
    if carpeta_ya_abierta(ruta_archivo):
        log.info("La carpeta ya estaba abierta: no se abre otra ventana.")
        return True
    # stdin/stdout a DEVNULL: si el Explorador heredara los de este proceso,
    # podría leer o escribir en el canal que usamos para hablar con Chrome.
    subprocess.Popen(f'explorer /select,"{ruta_archivo}"',
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)
    log.info("Carpeta abierta en el Explorador.")
    return False


# --- 4. Bucle principal ---

def atender(mensaje):
    nombre_archivo = (mensaje or {}).get("archivo")
    if not nombre_archivo:
        log.warning(f"Mensaje sin nombre de archivo: {mensaje}")
        return {"encontrado": False, "ruta": None, "archivo": nombre_archivo}

    inicio = time.monotonic()
    ruta, agotado = buscar_archivo(nombre_archivo)
    demora = time.monotonic() - inicio
    if agotado:
        log.warning(f"Búsqueda de '{nombre_archivo}' cortada a los {demora:.1f} s.")
    else:
        log.info(f"Búsqueda de '{nombre_archivo}' en {demora:.2f} s: {ruta or 'no está'}")

    ya_abierta = False
    if ruta:
        try:
            ya_abierta = mostrar_en_explorador(ruta)
        except Exception as error:
            log.error(f"No se pudo abrir el explorador: {error}")

    return {
        "encontrado": bool(ruta),
        "ruta": ruta,
        "archivo": nombre_archivo,
        "carpeta_ya_abierta": ya_abierta,
        "tiempo_agotado": agotado,
    }


if __name__ == '__main__':
    log.info("=== Buscador iniciado ===")
    while True:
        try:
            mensaje = leer_mensaje()
            if mensaje is None:
                break
            log.info(f"Mensaje recibido de Chrome: {mensaje}")
            enviar_mensaje(atender(mensaje))
        except Exception as e:
            log.exception(f"Error inesperado: {e}")
            break
