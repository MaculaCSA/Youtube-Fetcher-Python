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
# ¡IMPORTANTE! Se necesita scope de escritura para actualizar videos
SCOPES = ["https://www.googleapis.com/auth/youtube"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"
CSV_FILENAME = "videos_a_actualizar.csv" # Nombre del archivo CSV con los datos
# Usar un nombre de token diferente para el scope de escritura
TOKEN_PICKLE_FILE = 'token_youtube_write.pickle'
# Pausa entre actualizaciones (en segundos) para evitar errores de cuota
DELAY_BETWEEN_UPDATES = 1.5
# ------------------

def get_authenticated_service():
    """Autentica al usuario (con permisos de escritura) y devuelve el servicio API."""
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

def read_video_data_from_csv(filename):
    """Lee los datos de los videos desde un archivo CSV."""
    video_data = []
    if not os.path.exists(filename):
        print(f"Error Crítico: El archivo CSV '{filename}' no se encuentra en esta carpeta.")
        return None

    try:
        with open(filename, mode='r', encoding='utf-8', newline='') as csvfile:
            # Usar DictReader para acceder a columnas por nombre
            reader = csv.DictReader(csvfile)
            # Verificar si las columnas esperadas existen
            expected_columns = ['Título Corregido', 'ID de YouTube', 'Descripción']
            if not all(col in reader.fieldnames for col in expected_columns):
                print(f"Error Crítico: El archivo CSV '{filename}' no tiene las columnas esperadas: {expected_columns}")
                print(f"Columnas encontradas: {reader.fieldnames}")
                return None

            for row in reader:
                # Validar que los campos no estén vacíos (especialmente el ID)
                if not row.get('ID de YouTube'):
                    print(f"Advertencia: Fila saltada por no tener 'ID de YouTube': {row}")
                    continue
                video_data.append({
                    'title': row['Título Corregido'],
                    'id': row['ID de YouTube'],
                    'description': row['Descripción']
                })
        print(f"Se leyeron {len(video_data)} filas de datos del archivo '{filename}'.")
        return video_data
    except FileNotFoundError:
        print(f"Error Crítico: El archivo CSV '{filename}' no se pudo encontrar.")
        return None
    except Exception as e:
        print(f"Error inesperado al leer el archivo CSV '{filename}': {e}")
        return None

def get_video_details(youtube, video_id):
    """Obtiene los detalles actuales de un video, especialmente la categoryId."""
    try:
        response = youtube.videos().list(
            part="snippet", # Necesitamos snippet para obtener categoryId
            id=video_id
        ).execute()

        if not response.get("items"):
            print(f"  -> Error: No se encontró el video con ID '{video_id}'.")
            return None

        # Retorna el snippet completo, que incluye title, description, categoryId, etc.
        return response["items"][0]["snippet"]

    except HttpError as e:
        print(f"  -> Error HTTP obteniendo detalles de '{video_id}': {e.resp.status} {e.content}")
        return None
    except Exception as e:
        print(f"  -> Error inesperado obteniendo detalles de '{video_id}': {e}")
        return None

def update_video_metadata(youtube, video_id, new_title, new_description, current_category_id):
    """Actualiza el título y la descripción de un video específico."""
    print(f"  -> Intentando actualizar ID: {video_id}...")
    try:
        # El cuerpo de la solicitud necesita el ID y el snippet con los campos a actualizar
        # ¡IMPORTANTE! 'categoryId' es OBLIGATORIO en el snippet para la actualización
        update_body = {
            'id': video_id,
            'snippet': {
                'title': new_title,
                'description': new_description,
                'categoryId': current_category_id # Usar la categoría existente
                # Puedes añadir 'tags': ['nuevatag1', 'nuevatag2'] si también quieres actualizar etiquetas
            }
        }

        request = youtube.videos().update(
            part="snippet", # Indica que estamos enviando la parte 'snippet' en el body
            body=update_body
        )
        response = request.execute()
        print(f"  -> ÉXITO: Video '{response['snippet']['title']}' (ID: {video_id}) actualizado.")
        return True

    except HttpError as e:
        error_content = e.content.decode('utf-8') if isinstance(e.content, bytes) else str(e.content)
        print(f"  -> FALLO al actualizar ID: {video_id}. Error HTTP: {e.resp.status} {error_content}")
        if 'quota' in error_content.lower():
             print("  -> Posible error de cuota excedida. Considera aumentar el DELAY_BETWEEN_UPDATES.")
        return False
    except Exception as e:
        print(f"  -> FALLO al actualizar ID: {video_id}. Error inesperado: {e}")
        return False

def main():
    """Función principal del script."""
    print("--- Iniciando Script de Actualización de Metadatos de Videos ---")

    # 1. Autenticar con permisos de escritura
    youtube = get_authenticated_service()
    if not youtube:
        print("\nNo se pudo inicializar el servicio de YouTube. Saliendo.")
        sys.exit(1)

    # 2. Leer datos del CSV
    videos_to_update = read_video_data_from_csv(CSV_FILENAME)
    if videos_to_update is None:
        print("\nNo se pudieron leer los datos del CSV. Saliendo.")
        sys.exit(1)
    if not videos_to_update:
        print("\nEl archivo CSV está vacío o no contiene datos válidos. Saliendo.")
        sys.exit(1)

    # 3. Procesar cada video del CSV
    print("\n--- Comenzando Actualizaciones ---")
    success_count = 0
    fail_count = 0

    for i, video_info in enumerate(videos_to_update):
        video_id = video_info['id']
        new_title = video_info['title']
        new_description = video_info['description']

        print(f"\nProcesando video {i+1}/{len(videos_to_update)}: ID={video_id}, Nuevo Título='{new_title[:50]}...'") # Mostrar solo parte del título

        # 3a. Obtener detalles actuales (necesitamos categoryId)
        print("  -> Obteniendo detalles actuales (categoryId)...")
        current_snippet = get_video_details(youtube, video_id)

        if current_snippet:
            current_category_id = current_snippet.get('categoryId')
            if not current_category_id:
                print(f"  -> Error: No se pudo obtener la categoryId para el video {video_id}. Saltando actualización.")
                fail_count += 1
                continue # Pasar al siguiente video

            # 3b. Realizar la actualización
            if update_video_metadata(youtube, video_id, new_title, new_description, current_category_id):
                success_count += 1
            else:
                fail_count += 1
        else:
            # Si no se obtuvieron detalles, el video no existe o hubo error
            print(f"  -> No se pudieron obtener detalles para el video {video_id}. Saltando actualización.")
            fail_count += 1

        # 3c. Pausa para no exceder la cuota
        print(f"  -> Esperando {DELAY_BETWEEN_UPDATES} segundos...")
        time.sleep(DELAY_BETWEEN_UPDATES)

    # 4. Resumen Final
    print("\n--- Proceso de Actualización Finalizado ---")
    print(f"Resumen:")
    print(f"  Videos procesados: {len(videos_to_update)}")
    print(f"  Actualizaciones exitosas: {success_count}")
    print(f"  Actualizaciones fallidas: {fail_count}")
    print("-------------------------------------------")

if __name__ == "__main__":
    main()