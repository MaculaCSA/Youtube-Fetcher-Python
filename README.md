# Youtube-Uploader-Python
Script para subir de golpe todos los videos de una carpeta a youtube mediante la YouTube Data API v3

## Características
*   Autenticación segura mediante OAuth 2.0 (el usuario autoriza el acceso la primera vez).
*   Recupera videos de la playlist "Uploads" del canal.
*   Funciona con videos públicos y privados.
*   Permite especificar un `TARGET_YEAR` para filtrar videos por año de publicación.
*   Si `TARGET_YEAR` se deja como `None` el output serán todos los videos.
*   Genera un archivo CSV como columnas: `Título del video`, `ID de youtube`.

## **Proyecto en Google Cloud Platform:**
*   Ve a [Google Cloud Console](https://console.cloud.google.com/).
*   Crea un nuevo proyecto (o usa uno existente).
*   Habilita la API **"YouTube Data API v3"**.
*   Configura la **Pantalla de consentimiento de OAuth** (Tipo: Externo, añade tu email como usuario de prueba).
*   Crea **Credenciales** de tipo **"ID de cliente de OAuth"** para **"Aplicación de escritorio"**.
*   Añade usuarios de prueba a la pantalla de consentimiento
*   Descarga el archivo JSON de credenciales y renombrarlo como client_secret.json en esta misma carpeta.

## Requirements
```bash
pip install -r requirements.txt
```