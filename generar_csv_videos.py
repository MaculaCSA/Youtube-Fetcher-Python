import os
import csv
import pickle
from datetime import datetime # Para manejar fechas de publicación
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import sys # Para salir si hay errores críticos
import math # Para calcular lotes

### CONFIGURACIÓN ###
CLIENT_SECRETS_FILE = "client_secret.json" # Nombre del archivo descargado (asegúrate que exista)
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"] # Permiso de solo lectura
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"

# --- AJUSTE DE AÑO ---
# Pon el año específico (ej. 2025) o None para obtener todos los años.
TARGET_YEAR = None
TARGET_YEAR = 2025 # Ejemplo para obtener solo los de 2025

# Nombre del archivo para guardar el token de acceso (evita re-autorizar cada vez)
TOKEN_PICKLE_FILE = 'token_youtube_readonly.pickle'
# El nombre del archivo CSV de salida se generará dinámicamente más abajo
# ------------------

def get_authenticated_service():
    """Autentica al usuario usando OAuth 2.0 y devuelve un objeto de servicio API."""
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
                print(f"Error al refrescar el token: {e}. Se requiere nueva autorización.")
                if os.path.exists(TOKEN_PICKLE_FILE):
                    os.remove(TOKEN_PICKLE_FILE)
                credentials = None
                flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
                credentials = flow.run_local_server(port=0)
        else:
            if not os.path.exists(CLIENT_SECRETS_FILE):
                print(f"Error Crítico: No se encuentra el archivo '{CLIENT_SECRETS_FILE}'.")
                print("Asegúrate de haber descargado el archivo JSON de credenciales y guardado con ese nombre.")
                sys.exit(1)

            print("Se necesita autorización. Abriendo navegador...")
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            credentials = flow.run_local_server(port=0)

        with open(TOKEN_PICKLE_FILE, 'wb') as token:
            pickle.dump(credentials, token)
            print(f"Credenciales guardadas en '{TOKEN_PICKLE_FILE}' para futuras ejecuciones.")

    try:
        youtube_service = build(API_SERVICE_NAME, API_VERSION, credentials=credentials)
        print("Servicio de YouTube autenticado correctamente.")
        return youtube_service
    except HttpError as e:
        print(f"Error construyendo el servicio API: {e.resp.status} {e.content}")
        if os.path.exists(TOKEN_PICKLE_FILE):
            print(f"Intenta eliminar el archivo '{TOKEN_PICKLE_FILE}' y ejecutar el script de nuevo.")
        return None
    except Exception as e:
        print(f"Error inesperado construyendo el servicio: {e}")
        return None

def get_channel_uploads_playlist_id(youtube):
    """Obtiene el ID de la playlist 'Uploads' del canal autenticado."""
    try:
        print("Obteniendo ID de la playlist de subidas del canal...")
        channels_response = youtube.channels().list(
            part="contentDetails",
            mine=True
        ).execute()

        if not channels_response.get("items"):
            print("Error: No se pudo encontrar información del canal para el usuario autenticado.")
            return None

        playlist_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
        print(f"ID de Playlist 'Uploads' encontrado: {playlist_id}")
        return playlist_id

    except HttpError as e:
        print(f"Error HTTP obteniendo datos del canal: {e.resp.status} {e.content}")
        return None
    except Exception as e:
        print(f"Error inesperado obteniendo datos del canal: {e}")
        return None

def get_all_videos_from_playlist(youtube, playlist_id):
    """Recupera todos los items (videos) de una playlist, manejando paginación."""
    videos = []
    next_page_token = None
    count = 0

    print(f"Recuperando lista de videos de la playlist {playlist_id}...")
    while True:
        try:
            request = youtube.playlistItems().list(
                part="snippet", # Solo necesitamos snippet (título, fecha pub, ID recurso)
                playlistId=playlist_id,
                # ¡ADVERTENCIA SOBRE maxResults!
                # Se ha quitado maxResults=50 según solicitado.
                # ESTO HARÁ QUE LA API USE EL VALOR POR DEFECTO (5),
                # HACIENDO EL SCRIPT MÁS LENTO Y CONSUMIENDO MÁS CUOTA.
                # Se recomienda volver a añadir: maxResults=50,
                pageToken=next_page_token
            )
            response = request.execute()

            items = response.get("items", [])
            videos.extend(items)
            count += len(items)
            # Imprimir progreso con menos frecuencia si maxResults es bajo
            if count % 50 == 0 or not response.get("nextPageToken"): # Imprime cada 50 o al final
                 print(f"Recuperados {count} videos hasta ahora...")


            next_page_token = response.get("nextPageToken")

            if not next_page_token:
                print("Se han recuperado todos los videos de la playlist.")
                break

        except HttpError as e:
            print(f"\nError HTTP durante la paginación de videos: {e.resp.status} {e.content}")
            print("Puede ser un problema temporal o de cuota. Se detiene la recuperación.")
            break
        except Exception as e:
            print(f"\nError inesperado durante la paginación de videos: {e}")
            break

    print(f"Total de videos recuperados de la playlist: {len(videos)}")
    return videos

def get_video_statistics(youtube, video_ids):
    """Obtiene estadísticas (como likes) para una lista de IDs de vídeo."""
    stats = {}
    # La API permite hasta 50 IDs por solicitud
    batch_size = 50
    num_batches = math.ceil(len(video_ids) / batch_size)
    print(f"\nObteniendo estadísticas para {len(video_ids)} vídeos en {num_batches} lotes...")

    for i in range(num_batches):
        start_index = i * batch_size
        end_index = start_index + batch_size
        batch_ids = video_ids[start_index:end_index]
        ids_string = ",".join(batch_ids)
        print(f"Procesando lote {i+1}/{num_batches} ({len(batch_ids)} vídeos)...")

        try:
            request = youtube.videos().list(
                part="statistics", # Solo necesitamos las estadísticas
                id=ids_string
            )
            response = request.execute()

            for item in response.get("items", []):
                video_id = item.get("id")
                statistics = item.get("statistics", {})
                # El recuento de 'likes' puede no estar disponible si el propietario los oculta
                like_count = statistics.get("likeCount", "N/A")
                if video_id:
                    stats[video_id] = like_count

        except HttpError as e:
            print(f"Error HTTP obteniendo estadísticas para lote {i+1}: {e.resp.status} {e.content}")
            # Marcar los vídeos de este lote como no disponibles
            for vid in batch_ids:
                if vid not in stats:
                    stats[vid] = "Error"
        except Exception as e:
            print(f"Error inesperado obteniendo estadísticas para lote {i+1}: {e}")
            for vid in batch_ids:
                 if vid not in stats:
                    stats[vid] = "Error"

    print("Estadísticas de vídeo obtenidas.")
    return stats

def main():
    """Función principal del script."""
    youtube = get_authenticated_service()
    if not youtube:
        print("No se pudo inicializar el servicio de YouTube. Saliendo.")
        return

    uploads_playlist_id = get_channel_uploads_playlist_id(youtube)
    if not uploads_playlist_id:
        print("No se pudo obtener el ID de la playlist de subidas. Saliendo.")
        return

    all_videos_items = get_all_videos_from_playlist(youtube, uploads_playlist_id)

    if not all_videos_items:
        print("No se encontraron videos en la playlist de subidas o hubo un error al recuperarlos.")
        return

    # --- Obtener Estadísticas (Likes) ---
    all_video_ids = []
    for item in all_videos_items:
        video_id = item.get("snippet", {}).get("resourceId", {}).get("videoId")
        if video_id:
            all_video_ids.append(video_id)

    video_stats = {}
    if all_video_ids:
        video_stats = get_video_statistics(youtube, all_video_ids)
    else:
        print("No se encontraron IDs de vídeo válidos para obtener estadísticas.")
    # ------------------------------------

    # Determinar el nombre del archivo de salida basado en TARGET_YEAR
    if TARGET_YEAR is None:
        output_filename = "videos_youtube_all_years.csv"
        print("\nProcesando videos de TODOS los años.")
    else:
        output_filename = f"videos_youtube_{TARGET_YEAR}.csv"
        print(f"\nFiltrando videos publicados en el año {TARGET_YEAR}...")

    # Filtrar videos (si TARGET_YEAR tiene un valor) y añadir likes
    videos_seleccionados = []
    print("Procesando y filtrando vídeos...")
    for item in all_videos_items:
        snippet = item.get("snippet", {})
        published_at_str = snippet.get("publishedAt")
        title = snippet.get("title", "Sin Título")
        video_id = snippet.get("resourceId", {}).get("videoId")

        if not published_at_str or not video_id:
            print(f"Advertencia: Video '{title}' (Item ID: {item.get('id')}) sin fecha o ID. Saltando.")
            continue

        try:
            published_date = datetime.fromisoformat(published_at_str.replace('Z', '+00:00'))

            # Aplicar el filtro de año SOLO si TARGET_YEAR no es None
            if TARGET_YEAR is None or published_date.year == TARGET_YEAR:
                # Obtener los likes del diccionario de estadísticas
                likes = video_stats.get(video_id, "N/A") # Valor por defecto si no se encontró

                videos_seleccionados.append({
                    'Título del video': title,
                    'ID de youtube': video_id,
                    'Likes': likes # Añadir la nueva columna
                })

        except ValueError:
            print(f"Advertencia: Formato de fecha inesperado '{published_at_str}' para video '{title}'. Saltando.")
        except Exception as e:
            print(f"Error procesando fecha del video '{title}': {e}")

    # Escribir el archivo CSV
    if videos_seleccionados:
        print(f"\nSe encontraron {len(videos_seleccionados)} videos para incluir en el CSV.")
        print(f"Escribiendo resultados en '{output_filename}'...")
        try:
            with open(output_filename, 'w', newline='', encoding='utf-8') as csvfile:
                # Actualizar los nombres de campo para incluir 'Likes'
                fieldnames = ['Título del video', 'ID de youtube', 'Likes']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(videos_seleccionados)
            print(f"Archivo CSV '{output_filename}' creado con éxito.")

            # --- Encontrar el video con más likes ---
            video_mas_likes = None
            max_likes = -1

            for video in videos_seleccionados:
                try:
                    # Intentar convertir likes a entero, ignorar si no es posible
                    likes_actual = int(video['Likes'])
                    if likes_actual > max_likes:
                        max_likes = likes_actual
                        video_mas_likes = video
                except (ValueError, TypeError):
                    # Ignorar videos donde 'Likes' no sea un número válido (N/A, Error, etc.)
                    continue

            if video_mas_likes:
                titulo = video_mas_likes['Título del video']
                video_id = video_mas_likes['ID de youtube']
                likes_num = video_mas_likes['Likes'] # Mostrar el valor original (puede ser string)
                link = f"https://www.youtube.com/watch?v={video_id}"
                print("\n--- Vídeo con más likes ---")
                print(f"Título: {titulo}")
                print(f"ID: {video_id}")
                print(f"Likes: {likes_num}")
                print(f"Enlace: {link}")
            else:
                print("\nNo se encontraron vídeos con un número de likes válido para determinar el máximo.")
            # ------------------------------------

        except IOError as e:
            print(f"Error al escribir el archivo CSV '{output_filename}': {e}")
        except Exception as e:
             print(f"Error inesperado al escribir el CSV: {e}")
    else:
        if TARGET_YEAR is None:
            print("No se encontraron videos en total para generar el archivo CSV.")
        else:
            print(f"No se encontraron videos del año {TARGET_YEAR} para generar el archivo CSV.")

    print("\n--- Proceso Finalizado ---")

if __name__ == "__main__":
    main()