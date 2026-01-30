from google_auth_oauthlib.flow import Flow  # Flujo OAuth
from googleapiclient.discovery import build  # Constructor servicio
from googleapiclient.http import MediaFileUpload  # Para subir archivos
from django.conf import settings  # Settings
from datetime import datetime
from .models import Video  # Importamos tu modelo local
# from django.views import youtube


class YouTubeUploadService:
    """Servicio para subir videos a YouTube con OAuth"""
    
    def obtener_url_autorizacion(self):
        """Genera URL para que usuario autorice la app"""
        
        flow = Flow.from_client_config(  # Crea flujo OAuth
            {
                "web": {
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            },
            scopes=settings.YOUTUBE_SCOPES  # Permisos requeridos
        )
        
        flow.redirect_uri = settings.GOOGLE_REDIRECT_URI  # URL de callback
        
        authorization_url, state = flow.authorization_url(  # Genera URL
            access_type='offline',  # Obtener refresh_token
            include_granted_scopes='true'  # Incluir scopes ya autorizados
        )
        
        return authorization_url, state  # Retorna URL y state (para validación)
    
    def subir_video(self, credentials, archivo_path, titulo, descripcion, categoria='22', privacidad='private'):
        """
        Sube un video a YouTube
        
        Args:
            credentials: Credenciales OAuth del usuario
            archivo_path: Ruta al archivo de video
            titulo: Título del video
            descripcion: Descripción del video
            categoria: ID de categoría (22=People & Blogs, 27=Education)
            privacidad: public, private, unlisted
        
        Returns:
            dict: Información del video subido
        """
        
        # Crear servicio YouTube con credenciales del usuario
        youtube = build(  # Construye servicio autenticado
            'youtube', 
            'v3', 
            credentials=credentials  # Usa credentials del usuario
        )
        
        # Metadata del video
        body = {
            'snippet': {
                'title': titulo,  # Título
                'description': descripcion,  # Descripción
                'categoryId': categoria  # Categoría
            },
            'status': {
                'privacyStatus': privacidad  # Nivel de privacidad
            }
        }
        
        # Preparar archivo para upload
        media = MediaFileUpload(  # Crea objeto de media
            archivo_path,  # Ruta del archivo
            chunksize=-1,  # Subir todo de una vez
            resumable=True  # Permite reanudar si falla
        )
        
        # Ejecutar upload
        request = youtube.videos().insert(  # Crea request de insert
            part='snippet,status',  # Partes a enviar
            body=body,  # Metadata
            media_body=media  # Archivo de video
        )
        
        response = request.execute()  # Ejecuta upload (puede tomar tiempo)
        
#
        if 'id' in response:
            Video.objects.create(
                youtube_id=response['id'],
                titulo=titulo,
                descripcion=descripcion,
                fecha_publicacion=datetime.now()
            )

        return response  # Retorna respuesta con ID del video subido
    
    def actualizar_estadisticas_locales(self, credentials):
        youtube = build('youtube', 'v3', credentials=credentials)
        
        # 1. Traemos todos los IDs de videos que tenemos en MySQL
        videos_locales = Video.objects.all()
        if not videos_locales.exists():
            return

        ids_para_api = [v.youtube_id for v in videos_locales]

        # 2. Consultamos a YouTube por esos IDs (máximo 50 por llamada)
        response = youtube.videos().list(
            part="statistics",
            id=",".join(ids_para_api)
        ).execute()

        # 3. Guardamos los nuevos números en nuestra base de datos
        for item in response.get('items', []):
            Video.objects.filter(youtube_id=item['id']).update(
                vistas=int(item['statistics'].get('viewCount', 0)),
                likes=int(item['statistics'].get('likeCount', 0))
            )

    # def subir_video_con_thumbnail(video_file, thumbnail_file, metadata):
    #     # 1. Subir video
    #     media = MediaFileUpload(video_file, resumable=True)
    #     request = youtube.videos().insert(
    #         part='snippet,status',
    #         body={
    #             'snippet': metadata,
    #             'status': {'privacyStatus': 'public'}
    #         },
    #         media_body=media
    #     )
        
    #     response = request.execute()
    #     video_id = response['id']
        
    #     # 2. Subir thumbnail (requiere scope adicional)
    #     youtube.thumbnails().set(
    #         videoId=video_id,
    #         media_body=MediaFileUpload(thumbnail_file)
    #     ).execute()
        
    #     return video_id
    
    # def crear_playlist_automatica(titulo, descripcion, video_ids):
    #     # 1. Crear playlist
    #     playlist_response = youtube.playlists().insert(
    #         part='snippet,status',
    #         body={
    #             'snippet': {
    #                 'title': titulo,
    #                 'description': descripcion
    #             },
    #             'status': {'privacyStatus': 'public'}
    #         }
    #     ).execute()
        
    #     playlist_id = playlist_response['id']
        
    #     # 2. Agregar videos a playlist
    #     for video_id in video_ids:
    #         youtube.playlistItems().insert(
    #             part='snippet',
    #             body={
    #                 'snippet': {
    #                     'playlistId': playlist_id,
    #                     'resourceId': {
    #                         'kind': 'youtube#video',
    #                         'videoId': video_id
    #                     }
    #                 }
    #             }
    #         ).execute()
        
    #     return playlist_id