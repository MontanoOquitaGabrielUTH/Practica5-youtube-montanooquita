from googleapiclient.discovery import build  # Constructor de servicio Google
from django.conf import settings  # Configuración
from datetime import datetime  # Manejo de fechas
import isodate  # Para parsear duración ISO 8601
import hashlib
import re
# from django.views import youtube

from django.core.cache import cache
import logging


logger = logging.getLogger(__name__)

class YouTubeService2026:
    """Servicio YouTube Data API v3 - Optimizado 2026"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key or settings.YOUTUBE_API_KEY
        self.youtube = build(
            settings.YOUTUBE_API_SERVICE_NAME,
            settings.YOUTUBE_API_VERSION,
            developerKey=self.api_key
        )
    
    def buscar_videos_con_cache(self, query, max_results=10):
        """Busca videos con caché automático (2026 feature)"""
        
        # Generar clave de caché única
        cache_key = f"youtube_search_{hashlib.md5(query.encode()).hexdigest()}"
        
        # Intentar obtener de caché
        cached_result = cache.get(cache_key)
        if cached_result:
            logger.info(f"✅ Cache HIT: {query}")
            return cached_result
        
        # Si no existe en caché, llamar a API
        logger.info(f"🔍 API CALL: {query}")
        
        search_response = self.youtube.search().list(
            q=query,
            part='id,snippet',
            type='video',
            maxResults=max_results,
            order='relevance',
            regionCode='MX'  # México
        ).execute()
        
        resultados = search_response.get('items', [])
        
        # Guardar en caché por 1 hora
        cache.set(cache_key, resultados, timeout=3600)
        
        return resultados
    
    def obtener_estadisticas_mejoradas(self, video_id):
        """Obtiene estadísticas con métricas 2026"""
        
        response = self.youtube.videos().list(
            part='snippet,contentDetails,statistics,topicDetails',
            id=video_id
        ).execute()
        
        if not response['items']:
            return None
        
        video = response['items'][0]
        stats = video.get('statistics', {})
        
        return {
            'views': int(stats.get('viewCount', 0)),
            'likes': int(stats.get('likeCount', 0)),
            'comments': int(stats.get('commentCount', 0)),
            'engagement_rate': self._calcular_engagement(stats),  # 🆕 2026
        }

    def obtener_detalles_videos(self, video_ids):
        """
        Obtiene información detallada de videos
        
        Args:
            video_ids: Lista de IDs de videos o string único
        
        Returns:
            list: Información completa de videos
        """
        
        # Convertir a lista si es string
        if isinstance(video_ids, str):
            video_ids = [video_ids]  # Convierte a lista
        
        # Llamar endpoint videos.list
        videos_response = self.youtube.videos().list(  # Obtiene detalles
            id=','.join(video_ids),  # IDs separados por coma
            part='snippet,contentDetails,statistics'  # Incluye snippet, duración y stats
        ).execute()
        
        videos = []  # Lista para almacenar resultados
        
        for item in videos_response.get('items', []):  # Itera resultados
            snippet = item['snippet']  # Información básica
            statistics = item.get('statistics', {})  # Estadísticas (puede no existir)
            content = item['contentDetails']  # Detalles de contenido
            
            # Parsear duración ISO 8601 (PT15M30S → 15:30)
            duracion_iso = content.get('duration', 'PT0S')  # Obtiene duración
            duracion_segundos = isodate.parse_duration(duracion_iso).total_seconds()  # Convierte a segundos
            
            video_data = {  # Construye diccionario con datos
                'youtube_id': item['id'],  # ID del video
                'titulo': snippet['title'],  # Título
                'descripcion': snippet['description'],  # Descripción
                'canal_id': snippet['channelId'],  # ID del canal
                'canal_nombre': snippet['channelTitle'],  # Nombre del canal
                'fecha_publicacion': datetime.fromisoformat(  # Convierte a datetime
                    snippet['publishedAt'].replace('Z', '+00:00')
                ),
                'url_thumbnail': snippet['thumbnails']['high']['url'],  # Miniatura alta resolución
                'url_video': f"https://www.youtube.com/watch?v={item['id']}",  # URL completa
                'duracion': duracion_iso,  # Duración en formato ISO
                'duracion_segundos': int(duracion_segundos),  # Duración en segundos
                'vistas': int(statistics.get('viewCount', 0)),  # Visualizaciones
                'likes': int(statistics.get('likeCount', 0)),  # Me gusta
                'comentarios': int(statistics.get('commentCount', 0)),  # Comentarios
                'etiquetas': ','.join(snippet.get('tags', [])),  # Tags separados por coma
            }
            
            videos.append(video_data)  # Agrega a la lista
        
        return videos  # Retorna lista de videos
    
    def obtener_videos_canal(self, canal_id, max_resultados=20):
        """Obtiene videos de un canal específico"""
        
        search_response = self.youtube.search().list(
            channelId=canal_id,  # Filtrar por canal
            part='id',
            type='video',
            order='date',  # Más recientes primero
            maxResults=max_resultados
        ).execute()
        
        video_ids = [item['id']['videoId'] for item in search_response.get('items', [])]
        
        if video_ids:
            return self.obtener_detalles_videos(video_ids)
        
        return []
    
    def _calcular_engagement(self, stats):
        """Calcula tasa de engagement (2026 metric)"""
        views = int(stats.get('viewCount', 0))
        if views == 0:
            return 0.0
        
        likes = int(stats.get('likeCount', 0))
        comments = int(stats.get('commentCount', 0))
        
        engagement = ((likes + comments) / views) * 100
        return round(engagement, 2)
    
    # def buscar_videos_seguro(query):
    #     # Validar longitud
    #     if len(query) < 3 or len(query) > 100:
    #         raise ValueError("Query debe tener entre 3-100 caracteres")
        
    #     # Sanitizar caracteres especiales
    #     query_sanitizado = re.sub(r'[^\w\s-]', '', query)
        
    #     return youtube.search().list(
    #         q=query_sanitizado,
    #         part='snippet',
    #         type='video',
    #         maxResults=10
    #     ).execute()

    # def buscar_videos_con_cache(query, max_results=10):
    #     # Generar clave única para cache
    #     cache_key = f"youtube_search_{hashlib.md5(query.encode()).hexdigest()}_{max_results}"
        
    #     # Intentar obtener de cache
    #     resultados = cache.get(cache_key)
        
    #     if resultados:
    #         logger.info(f"Búsqueda '{query}' obtenida de cache")
    #         return resultados
        
    #     # Si no está en cache, llamar a API
    #     logger.info(f"Búsqueda '{query}' llamando a YouTube API")
    #     response = youtube.search().list(
    #         q=query,
    #         part='snippet',
    #         type='video',
    #         maxResults=max_results
    #     ).execute()
        
    #     resultados = response.get('items', [])
        
    #     # Guardar en cache por 1 hora (3600 segundos)
    #     cache.set(cache_key, resultados, timeout=3600)
        
    #     return resultados

    # def obtener_detalles_multiples(video_ids):
    #     # video_ids = ["dQw4w9WgXcQ", "abc123xyz", ...]
        
    #     # Unir IDs con coma (máximo 50)
    #     ids_str = ','.join(video_ids[:50])
        
    #     response = youtube.videos().list(
    #         part='snippet,contentDetails,statistics',
    #         id=ids_str  # ← Múltiples IDs
    #     ).execute()
        
    #     return response.get('items', [])

    # def obtener_videos_paginados(channel_id, page_token=None):
    #     request = youtube.search().list(
    #         channelId=channel_id,
    #         part='snippet',
    #         type='video',
    #         maxResults=50,  # Max permitido
    #         pageToken=page_token  # Token de página siguiente
    #     )
        
    #     response = request.execute()
        
    #     return {
    #         'videos': response.get('items', []),
    #         'next_page_token': response.get('nextPageToken'),
    #         'total_results': response['pageInfo']['totalResults']
    #     }
    
    # def obtener_detalles_multiples(video_ids):
    #     # video_ids = ["dQw4w9WgXcQ", "abc123xyz", ...]
        
    #     # Unir IDs con coma (máximo 50)
    #     ids_str = ','.join(video_ids[:50])
        
    #     response = youtube.videos().list(
    #         part='snippet,contentDetails,statistics',
    #         id=ids_str  # ← Múltiples IDs
    #     ).execute()
        
    #     return response.get('items', [])

    # # Uso:
    # video_ids = ["dQw4w9WgXcQ", "abc123", "xyz789"]
    # detalles = obtener_detalles_multiples(video_ids)
    # # Consume solo 1 unidad de cuota (vs 3 si los pides por separado)

    # def obtener_analytics_videos(channel_id):
    #     # Obtener videos del canal
    #     videos_response = youtube.search().list(
    #         channelId=channel_id,
    #         part='id',
    #         type='video',
    #         maxResults=50
    #     ).execute()
        
    #     video_ids = [item['id']['videoId'] for item in videos_response['items']]
        
    #     # Obtener estadísticas (batch)
    #     stats_response = youtube.videos().list(
    #         part='snippet,statistics',
    #         id=','.join(video_ids)
    #     ).execute()
        
    #     analytics = []
    #     for video in stats_response['items']:
    #         analytics.append({
    #             'titulo': video['snippet']['title'],
    #             'views': int(video['statistics'].get('viewCount', 0)),
    #             'likes': int(video['statistics'].get('likeCount', 0)),
    #             'comentarios': int(video['statistics'].get('commentCount', 0)),
    #             'fecha_publicacion': video['snippet']['publishedAt']
    #         })
        
    #     # Ordenar por views
    #     analytics.sort(key=lambda x: x['views'], reverse=True)
        
    #     return analytics