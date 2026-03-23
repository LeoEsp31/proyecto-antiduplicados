import sys
import struct
import json
import os
from pathlib import Path
import logging
import subprocess

# Configuramos el sistema de logs para poder ver qué pasa en segundo plano
# Esto va a crear un archivo 'debug_buscador.log' en la misma carpeta que este script
ruta_log = os.path.join(os.path.dirname(__file__), 'debug_buscador.log')
logging.basicConfig(filename=ruta_log, level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# --- 1. Lógica de comunicación con Chrome (Native Messaging) ---

def leer_mensaje():
    """Lee el mensaje que manda Chrome desde la entrada estándar (stdin)."""
    # Leemos los primeros 4 bytes que indican el tamaño del mensaje
    raw_length = sys.stdin.buffer.read(4)
    if len(raw_length) == 0:
        sys.exit(0)
    
    # Desempaquetamos esos 4 bytes para obtener el número entero
    message_length = struct.unpack('@I', raw_length)[0]
    
    # Leemos el mensaje real en base al tamaño que nos pasaron
    message = sys.stdin.buffer.read(message_length).decode('utf-8')
    return json.loads(message)

def enviar_mensaje(mensaje_dict):
    """Empaqueta un diccionario en JSON y lo manda a Chrome por la salida estándar (stdout)."""
    mensaje_json = json.dumps(mensaje_dict).encode('utf-8')
    # Empaquetamos la longitud en 4 bytes (formato 'I' = unsigned int)
    header = struct.pack('@I', len(mensaje_json))
    
    sys.stdout.buffer.write(header)
    sys.stdout.buffer.write(mensaje_json)
    sys.stdout.buffer.flush()

# --- 2. Lógica de búsqueda en el disco duro ---

def buscar_archivo(nombre_archivo, directorio_base):
    """Busca el archivo de forma recursiva ignorando errores de permisos."""
    try:
        for ruta in Path(directorio_base).rglob(nombre_archivo):
            return str(ruta)
    except PermissionError:
        pass
    return None

# --- 3. Bucle principal (El servidor que se queda escuchando) ---

if __name__ == '__main__':
    # Definimos dónde buscar (tu carpeta de usuario de Windows)
    carpeta_usuario = os.path.expanduser("~")
    logging.info("=== Buscador iniciado. Esperando mensajes de Chrome ===")
    
    while True:
        try:
            # 1. Esperamos que la extensión nos mande el JSON
            mensaje_recibido = leer_mensaje()
            logging.info(f"Mensaje recibido de Chrome: {mensaje_recibido}")
            
            nombre_archivo = mensaje_recibido.get("archivo")
            
            if nombre_archivo:
                logging.info(f"Iniciando búsqueda de: '{nombre_archivo}' en {carpeta_usuario}")
                ruta_encontrada = buscar_archivo(nombre_archivo, carpeta_usuario)
                
                # --- NUEVA MAGIA: ABRIR CARPETA ---
                if ruta_encontrada:
                    try:
                        # El comando /select le dice a Windows que abra la carpeta 
                        # y deje el archivo resaltado/seleccionado
                        subprocess.Popen(f'explorer /select,"{ruta_encontrada}"')
                        logging.info("Carpeta abierta exitosamente en Windows.")
                    except Exception as error_explorer:
                        logging.error(f"No se pudo abrir el explorador: {error_explorer}")
                # ----------------------------------

                respuesta = {
                    "encontrado": bool(ruta_encontrada),
                    "ruta": ruta_encontrada,
                    "archivo": nombre_archivo
                }
                
                enviar_mensaje(respuesta)
            else:
                logging.warning("El mensaje recibido no contenía un nombre de archivo válido.")
                
        except Exception as e:
            logging.error(f"Ocurrió un error fatal: {e}")
            sys.exit(0)