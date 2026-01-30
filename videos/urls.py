from django.urls import path
from . import views
# from .youtube_upload import mis_videos, subir_video

app_name = 'videos'  # Namespace para URLs

urlpatterns = [
    # ========== PÁGINAS PRINCIPALES ==========
    path('', views.inicio, name='inicio'),
    
    # ========== OAUTH YOUTUBE ==========
    path('oauth/authorize/', views.oauth_authorize, name='oauth_authorize'),
    path('oauth/callback/', views.oauth_callback, name='oauth_callback'),
    
    # ========== GESTIÓN DE VIDEOS ==========
    path('buscar/', views.buscar_videos, name='buscar_videos'),
    path('video/<str:video_id>/', views.detalle_video, name='detalle_video'),
    path('mis-videos/', views.mis_videos, name='mis_videos'),
    
    # ========== SUBIR VIDEOS ==========
    path('subir/', views.subir_video, name='subir_video'),
    path('subir/procesar/', views.procesar_subida, name='procesar_subida'),
]