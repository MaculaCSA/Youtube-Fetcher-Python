import os
import csv
import pickle
import time
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import sys

### CONFIGURACIÓN ###
CLIENT_SECRETS_FILE = "client_secret.json" # Tu archivo de credenciales
# Se necesita scope de escritura para intentar modificar videos
SCOPES = ["https://www.googleapis.com/auth/youtube"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
CSV_FILENAME = "videos_ocultar_likes.csv" # CSV con la columna 'ID de YouTube'
# Usar un nombre de token diferente por si los scopes cambian
TOKEN_PICKLE_FILE = 'token_youtube_write_likes.pickle'
# Pausa entre intentos de actualización (en segundos)
DELAY_BETWEEN_UPDATES = 1.5
# ------------------

def get_authenticated_service():
    """Autentica al usuario (con permisos de escritura) y devuelve el servicio API."""
    # (Misma función de autenticación que el script 'actualizar_metadata_videos.py')
    # ... [Copia aquí la función get_authenticated_service completa del script anterior] ...
    # ... Asegúrate de que usa TOKEN_PICKLE_FILE y SCOPES definidos arriba ...

    # --- INICIO COPIA get_authenticated_service ---
    credentials = None
    if os.path.exists(TOKEN_PICKLE_FILE):
        with open(TOKEN_PICKLE_FILE, 'rb') as token:
            try:
                credentials = pickle.load(token)
            except (pickle.UnpicklingError, EOFError):
                 print(f"Advertencia: No se pudo leer {TOKEN_PICKLE_FILE}. Se solicitará autorización.")
                 credentials = None

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            print("Refrescando token de acceso...")
            try:
                credentials.refresh(Request())
            except Exception as e:
                print(f"Error al refrescar el token ({type(e).__name__}): {e}. Se requiere nueva autorización.")
                if os.path.exists(TOKEN_PICKLE_FILE):
                    try:
                        os.remove(TOKEN_PICKLE_FILE)
                        print(f"Archivo de token '{TOKEN_PICKLE_FILE}' eliminado.")
                    except OSError as oe:
                        print(f"Error eliminando el archivo de token: {oe}")
                credentials = None # Fuerza el flujo de abajo
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
                credentials = flow.run_local_server(port=0)
        else:
            if not os.path.exists(CLIENT_SECRETS_FILE):
                print(f"Error Crítico: No se encuentra el archivo '{CLIENT_SECRETS_FILE}'.")
                print("Asegúrate de haber descargado el archivo JSON de credenciales y guardado con ese nombre.")
                sys.exit(1)

            print(f"Se necesita autorización para la cuenta de YouTube con permisos de modificación ({SCOPES[0]}).")
            print("Abriendo navegador...")
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            credentials = flow.run_local_server(port=0)

        with open(TOKEN_PICKLE_FILE, 'wb') as token:
            pickle.dump(credentials, token)
            print(f"Credenciales de escritura guardadas en '{TOKEN_PICKLE_FILE}'.")

    try:
        youtube_service = build(API_SERVICE_NAME, API_VERSION, credentials=credentials)
        print("Servicio de YouTube (con permisos de escritura) autenticado correctamente.")
        return youtube_service
    except HttpError as e:
        print(f"Error construyendo el servicio API: {e.resp.status} {e.content}")
        if os.path.exists(TOKEN_PICKLE_FILE):
            print(f"Intenta eliminar el archivo '{TOKEN_PICKLE_FILE}' y ejecutar de nuevo.")
        return None
    except Exception as e:
        print(f"Error inesperado construyendo el servicio: {e}")
        return None
    # --- FIN COPIA get_authenticated_service ---


def read_video_ids_from_csv(filename):
    """Lee solo los IDs de video desde un archivo CSV."""
    video_ids = []
    if not os.path.exists(filename):
        print(f"Error Crítico: El archivo CSV '{filename}' no se encuentra.")
        return None

    try:
        with open(filename, mode='r', encoding='utf-8', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            id_column_name = 'ID de YouTube' # Nombre exacto de la columna

            if id_column_name not in reader.fieldnames:
                print(f"Error Crítico: El archivo CSV '{filename}' no contiene la columna requerida: '{id_column_name}'")
                print(f"Columnas encontradas: {reader.fieldnames}")
                return None

            for row in reader:
                video_id = row.get(id_column_name)
                if video_id:
                    video_ids.append(video_id.strip()) # Quitar espacios extra
                else:
                    print(f"Advertencia: Fila saltada por no tener '{id_column_name}': {row}")

        if not video_ids:
             print(f"No se encontraron IDs de video válidos en la columna '{id_column_name}' del archivo '{filename}'.")
             return None

        print(f"Se leyeron {len(video_ids)} IDs de video del archivo '{filename}'.")
        return video_ids
    except FileNotFoundError:
        print(f"Error Crítico: El archivo CSV '{filename}' no se pudo encontrar.")
        return None
    except Exception as e:
        print(f"Error inesperado al leer el archivo CSV '{filename}': {e}")
        return None


def attempt_to_hide_likes(youtube, video_id):
    """
    Intenta actualizar el video para ocultar los 'likes'.
    ADVERTENCIA: No hay un método API documentado estándar para esto.
                 Esta función probablemente fallará o no tendrá efecto.
    """
    print(f"  -> Intentando modificar estado de 'likes' para ID: {video_id}...")
    print("     ADVERTENCIA: La API de YouTube no tiene un método documentado claro para ocultar solo los 'likes'. Este intento puede fallar.")

    # ---- INICIO SECCIÓN HIPOTÉTICA ----
    # Si existiera un campo (EJEMPLO HIPOTÉTICO, PROBABLEMENTE INCORRECTO):
    # update_body = {
    #     'id': video_id,
    #     'status': {
    #         'showRatings': False # CAMPO INVENTADO - NO USAR EN PRODUCCIÓN
    #         # O quizás: 'likeCountVisible': False # OTRO CAMPO INVENTADO
    #     }
    # }
    # request = youtube.videos().update(
    #     part="status", # Parte a actualizar
    #     body=update_body
    # )
    # try:
    #     response = request.execute()
    #     print(f"  -> POSIBLE ÉXITO (verificar manualmente): Estado del video {video_id} modificado.")
    #     return True # Asumimos éxito si la API no da error
    # except HttpError as e:
    #     error_content = e.content.decode('utf-8') if isinstance(e.content, bytes) else str(e.content)
    #     print(f"  -> FALLO esperado al actualizar ID: {video_id}. Error HTTP: {e.resp.status} {error_content}")
    #     if "invalidPart" in error_content or "invalidParameter" in error_content:
    #          print("     -> Error sugiere que el campo/parte intentado no es válido/modificable.")
    #     return False
    # except Exception as e:
    #     print(f"  -> FALLO inesperado al actualizar ID: {video_id}. Error: {e}")
    #     return False
    # ---- FIN SECCIÓN HIPOTÉTICA ----

    # --- Como no hay método fiable, informamos y no hacemos nada ---
    print(f"  -> ACCIÓN OMITIDA: No se puede ocultar el contador de 'likes' de forma fiable mediante la API para {video_id}.")
    return None # Indica que la acción no fue posible/realizada


def main():
    """Función principal del script."""
    print("--- Iniciando Script para Intentar Ocultar Likes de Videos ---")
    print("*** ADVERTENCIA: La API de YouTube V3 NO proporciona una forma documentada y fiable para ocultar solo el recuento de 'Me Gusta'. Este script NO realizará cambios efectivos. ***")

    # 1. Autenticar (necesita permisos de escritura por si acaso se descubriera un método)
    youtube = get_authenticated_service()
    if not youtube:
        print("\nNo se pudo inicializar el servicio de YouTube. Saliendo.")
        sys.exit(1)

    # 2. Leer IDs del CSV
    video_ids_to_process = read_video_ids_from_csv(CSV_FILENAME)
    if video_ids_to_process is None:
        print("\nNo se pudieron leer los IDs del CSV. Saliendo.")
        sys.exit(1)

    # 3. Procesar cada ID de video
    print("\n--- Procesando Videos (Simulación/Intento) ---")
    processed_count = 0
    skipped_count = 0 # Contará los que no se pudieron procesar por no haber método

    for i, video_id in enumerate(video_ids_to_process):
        print(f"\nProcesando video {i+1}/{len(video_ids_to_process)}: ID={video_id}")

        # Intentar la acción (que informará que no es posible)
        result = attempt_to_hide_likes(youtube, video_id)
        processed_count +=1
        if result is None:
            skipped_count += 1 # Contamos como omitido/no posible

        # Pausa igualmente para simular un flujo de trabajo real y no saturar (si hubiera llamadas)
        print(f"  -> Esperando {DELAY_BETWEEN_UPDATES} segundos...")
        time.sleep(DELAY_BETWEEN_UPDATES)

    # 4. Resumen Final
    print("\n--- Proceso Finalizado ---")
    print(f"Resumen:")
    print(f"  Videos en el CSV: {len(video_ids_to_process)}")
    print(f"  Videos procesados (intentos/omitidos): {processed_count}")
    print(f"  Acciones omitidas (método API no disponible): {skipped_count}")
    print("\nRecordatorio: No se realizaron cambios efectivos en la visibilidad de 'likes' debido a limitaciones de la API.")
    print("-------------------------------------------")


if __name__ == "__main__":
    main()