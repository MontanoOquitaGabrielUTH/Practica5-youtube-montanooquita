from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.conf import settings
import os
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Google API Client
from google.oauth2.credentials import Credentials
from django.db.models import Sum, Q
from google_auth_oauthlib.flow import Flow
from .youtube_service import YouTubeService2026
from .upload_service import YouTubeUploadService
from django.core.files.storage import default_storage

from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


from datetime import datetime

from .models import Video

def inicio(request):
    """Dashboard principal con estadísticas globales de la base de datos"""
    # 1. Obtenemos los últimos 12 para mostrar en la galería
    videos_recientes = Video.objects.all().order_by('-fecha_publicacion')[:12]
    
    creds_data = request.session.get('youtube_credentials')
        
    # Si hay sesión iniciada, refrescamos datos antes de mostrar el dashboard
    if creds_data:
        from google.oauth2.credentials import Credentials
        service = YouTubeUploadService()
        service.actualizar_estadisticas_locales(Credentials(**creds_data))

    # Ahora sí, leemos de la base de datos ya actualizada
    videos_recientes = Video.objects.all().order_by('-fecha_publicacion')[:12]
    stats_globales = Video.objects.aggregate(
        total_vistas=Sum('vistas'),
        total_likes=Sum('likes')
    )

    contexto = {
        'videos': videos_recientes,
        'total_videos': Video.objects.count(),
        'total_views': stats_globales['total_vistas'] or 0,
        'total_likes': stats_globales['total_likes'] or 0,
    }
    return render(request, 'videos/inicio.html', contexto)


def mis_videos(request):
    creds_data = request.session.get('youtube_credentials')
    if not creds_data:
        return redirect('videos:oauth_authorize')

    try:
        credentials = Credentials(**creds_data)
        youtube = build('youtube', 'v3', credentials=credentials)

        # 1. SINCRONIZACIÓN: Traemos de YouTube y guardamos en MySQL
        # Esto asegura que el buscador TENGA algo que buscar
        canal_res = youtube.channels().list(part="contentDetails", mine=True).execute()
        uploads_id = canal_res['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        
        videos_api = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=uploads_id,
            maxResults=50
        ).execute()

        for item in videos_api.get('items', []):
            v_id = item['contentDetails']['videoId']
            thumbnails = item['snippet'].get('thumbnails', {})
            url_thumb = (thumbnails.get('high') or thumbnails.get('medium') or thumbnails.get('default', {})).get('url', '')

            # Guardamos o actualizamos en MySQL
            Video.objects.update_or_create(
                youtube_id=v_id,
                defaults={
                    'titulo': item['snippet']['title'],
                    'descripcion': item['snippet']['description'],
                    'url_thumbnail': url_thumb,
                    'fecha_publicacion': item['snippet']['publishedAt'],
                    # Nota: Aquí podrías llamar a las stats solo una vez para todos los IDs
                }
            )

        # 2. LÓGICA DE DJANGO (Buscador y Filtros sobre MySQL)
        queryset = Video.objects.all().order_by('-fecha_publicacion')
        
        query = request.GET.get('buscar')
        if query:
            queryset = queryset.filter(Q(titulo__icontains=query) | Q(descripcion__icontains=query))

        # 3. ESTADÍSTICAS GLOBALES (Sobre los videos filtrados)
        stats = queryset.aggregate(
            v_vistas=Sum('vistas'),
            v_likes=Sum('likes')
        )

        return render(request, 'videos/mis_videos.html', {
            'videos': queryset, # Enviamos el QuerySet de MySQL
            'total_views': stats['v_vistas'] or 0,
            'total_likes': stats['v_likes'] or 0,
            'total_videos': queryset.count(),
        })

    except Exception as e:
        messages.error(request, f"Error: {e}")
        return redirect('videos:inicio')

# @login_required
def oauth_authorize(request):
    """Redirige a Google OAuth para autorización"""
    flow = Flow.from_client_secrets_file(
        'client_secrets.json',
        scopes=settings.YOUTUBE_SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI
    )
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    
    request.session['oauth_state'] = state
    return redirect(authorization_url)

def subir_video(request):
    # UNIFICADO: usamos 'youtube_credentials'
    if 'youtube_credentials' not in request.session:
        return redirect('videos:oauth_authorize')

    if request.method == 'POST':
        titulo = request.POST.get('titulo')
        descripcion = request.POST.get('descripcion')
        categoria = request.POST.get('categoria', '27') 
        privacidad = request.POST.get('privacidad', 'private')
        archivo = request.FILES.get('video')

        if archivo:
            path_temporal = default_storage.save(f'tmp/{archivo.name}', archivo)
            ruta_completa = os.path.join(settings.MEDIA_ROOT, path_temporal)

            try:
                creds_data = request.session.get('youtube_credentials')
                credentials = Credentials(**creds_data)
                uploader = YouTubeUploadService()

                uploader.subir_video(
                    credentials=credentials,
                    archivo_path=ruta_completa,
                    titulo=titulo,
                    descripcion=descripcion,
                    categoria=categoria,
                    privacidad='public' 
                )

                messages.success(request, "¡Video subido exitosamente a YouTube!")
            except Exception as e:
                messages.error(request, f"Error al subir: {e}")
            finally:
                if os.path.exists(ruta_completa):
                    os.remove(ruta_completa)
            
            return redirect('videos:mis_videos')
        
    return render(request, 'videos/subir_video.html')

# ELIMINADO @login_required para evitar el error 404
def oauth_callback(request):
    """Recibe código de autorización y obtiene tokens"""
    state = request.session.get('oauth_state')
    
    try:
        flow = Flow.from_client_secrets_file(
            'client_secrets.json',
            scopes=settings.YOUTUBE_SCOPES,
            state=state,
            redirect_uri=settings.GOOGLE_REDIRECT_URI
        )
        
        flow.fetch_token(authorization_response=request.build_absolute_uri())
        credentials = flow.credentials
        
        request.session['youtube_credentials'] = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
        }
        
        # Limpiamos el state de la sesión para evitar errores de CSRF en el futuro
        if 'oauth_state' in request.session:
            del request.session['oauth_state']
            
        messages.success(request, '✅ Conectado con YouTube')
        return redirect('videos:inicio')
        
    except Exception as e:
        messages.error(request, f'❌ Error OAuth: {e}')
        return redirect('videos:inicio')
    
def buscar_videos(request):
    """Busca videos en YouTube por palabra clave"""
    query = request.GET.get('q', '')
    resultados = []
    
    if query:
        youtube = build(
            settings.YOUTUBE_API_SERVICE_NAME,
            settings.YOUTUBE_API_VERSION,
            developerKey=settings.YOUTUBE_API_KEY
        )
        
        search_response = youtube.search().list(
            q=query,
            part='id,snippet',
            type='video',
            maxResults=20
        ).execute()
        
        resultados = search_response.get('items', [])
    
    return render(request, 'videos/buscar.html', {
        'query': query,
        'resultados': resultados
    })

# ELIMINADO @login_required para evitar el error 404
def procesar_subida(request):
    """Sube video a YouTube usando OAuth del usuario"""
    if request.method == 'POST':
        try:
            creds_data = request.session.get('youtube_credentials')
            credentials = Credentials(**creds_data)
            
            youtube = build('youtube', 'v3', credentials=credentials)
            
            video_file = request.FILES['video']
            titulo = request.POST.get('titulo')
            descripcion = request.POST.get('descripcion')
            
            temp_path = f'/tmp/{video_file.name}'
            with open(temp_path, 'wb') as f:
                for chunk in video_file.chunks():
                    f.write(chunk)
            
            body = {
                'snippet': {
                    'title': titulo,
                    'description': descripcion,
                    'categoryId': '27'
                },
                'status': {'privacyStatus': 'private'}
            }
            
            media = MediaFileUpload(temp_path, resumable=True)
            
            request_upload = youtube.videos().insert(
                part='snippet,status',
                body=body,
                media_body=media
            )
            
            response = request_upload.execute()
            os.remove(temp_path)
            
            messages.success(request, f'✅ Video subido: {response["id"]}')
            return redirect('videos:mis_videos')
            
        except Exception as e:
            messages.error(request, f'❌ Error: {e}')
    
    return render(request, 'videos/subir_video.html')

def detalle_video(request, video_id):
    """Muestra los detalles de un video específico usando la API de YouTube"""
    # UNIFICADO: usamos 'youtube_credentials'
    creds_data = request.session.get('youtube_credentials')
    if not creds_data:
        return redirect('videos:oauth_authorize')

    try:
        credentials = Credentials(**creds_data)
        youtube = build('youtube', 'v3', credentials=credentials)

        res = youtube.videos().list(
            part="snippet,statistics,contentDetails",
            id=video_id
        ).execute()

        if not res['items']:
            messages.error(request, "Video no encontrado.")
            return redirect('videos:mis_videos')

        item = res['items'][0]
        video_data = {
            'youtube_id': video_id,
            'titulo': item['snippet']['title'],
            'descripcion': item['snippet']['description'],
            'vistas': item['statistics'].get('viewCount', 0),
            'likes': item['statistics'].get('likeCount', 0),
            'comentarios': item['statistics'].get('commentCount', 0),
            'fecha_publicacion': item['snippet']['publishedAt'],
            'canal_nombre': item['snippet']['channelTitle'],
            'canal_id': item['snippet']['channelId'],
            'get_embed_url': f"https://www.youtube.com/embed/{video_id}",
            'url_video': f"https://www.youtube.com/watch?v={video_id}",
        }

        return render(request, 'videos/detalle_video.html', {'video': video_data})

    except Exception as e:
        messages.error(request, f"Error al cargar el video: {e}")
        return redirect('videos:mis_videos')