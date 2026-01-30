from django.db import models  # ORM de Django
from django.contrib.auth.models import User  # Usuario
from cryptography.fernet import Fernet
from django.conf import settings
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class Video(models.Model):
    """Modelo para almacenar información de videos de YouTube"""
    
    # Información de YouTube
    youtube_id = models.CharField(max_length=20, unique=True)  # ID único de YouTube (11 chars)
    titulo = models.CharField(max_length=300)  # Título del video
    descripcion = models.TextField()  # Descripción completa
    
    # URLs
    url_video = models.URLField()  # https://youtube.com/watch?v=xxxxx
    url_thumbnail = models.URLField()  # URL de la miniatura (imagen)
    
    # Información del canal
    canal_id = models.CharField(max_length=50)  # ID del canal de YouTube
    canal_nombre = models.CharField(max_length=200)  # Nombre del canal
    
    # Detalles
    duracion = models.CharField(max_length=20, blank=True)  # Formato ISO 8601 (PT15M30S)
    fecha_publicacion = models.DateTimeField()  # Cuándo se publicó en YouTube
    
    # Estadísticas (se actualizan periódicamente)
    vistas = models.BigIntegerField(default=0)  # Visualizaciones en YouTube
    likes = models.IntegerField(default=0)  # Me gusta
    comentarios = models.IntegerField(default=0)  # Cantidad de comentarios
    
    # Categorización local
    categoria = models.CharField(max_length=50, choices=[  # Categorías personalizadas
        ('programacion', 'Programación'),
        ('bases_datos', 'Bases de Datos'),
        ('redes', 'Redes'),
        ('seguridad', 'Seguridad'),
        ('otro', 'Otro'),
    ])
    etiquetas = models.CharField(max_length=500, blank=True)  # Tags separados por comas
    
    # Relaciones
    agregado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)  # Usuario que agregó
    
    # Metadatos
    creado = models.DateTimeField(auto_now_add=True)  # Fecha de creación en BD local
    actualizado = models.DateTimeField(auto_now=True)  # Última actualización
    
    class Meta:
        ordering = ['-fecha_publicacion']  # Más recientes primero
        verbose_name_plural = 'Videos'
    
    def __str__(self):
        return self.titulo
    
    def get_embed_url(self):
        """Retorna URL para embed iframe"""
        return f"https://www.youtube.com/embed/{self.youtube_id}"  # Para <iframe>


class Playlist(models.Model):
    """Playlist personalizada de videos"""
    
    nombre = models.CharField(max_length=200)  # Nombre de la playlist
    descripcion = models.TextField(blank=True)  # Descripción
    videos = models.ManyToManyField(Video, related_name='playlists')  # Videos incluidos
    creador = models.ForeignKey(User, on_delete=models.CASCADE)  # Dueño de la playlist
    publica = models.BooleanField(default=False)  # Si es visible para todos
    
    creado = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.nombre
    
class YouTubeToken(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    access_token = models.TextField()  # Expira en 1h, no crítico
    refresh_token_encrypted = models.TextField()  # ← Cifrado
    token_expiry = models.DateTimeField()
    
    def encrypt_refresh_token(self, token):
        cipher = Fernet(settings.FERNET_KEY)
        return cipher.encrypt(token.encode()).decode()
    
    def decrypt_refresh_token(self):
        cipher = Fernet(settings.FERNET_KEY)
        return cipher.decrypt(self.refresh_token_encrypted.encode()).decode()
    
class QuotaUsage(models.Model):
    fecha = models.DateField(auto_now_add=True)
    operacion = models.CharField(max_length=50)  # search, upload, etc.
    unidades = models.IntegerField()
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    
    class Meta:
        indexes = [
            models.Index(fields=['fecha'])
        ]

def registrar_uso_cuota(operacion, unidades, usuario):
    QuotaUsage.objects.create(
        operacion=operacion,
        unidades=unidades,
        usuario=usuario
    )
    
    # Verificar si excede límite diario
    hoy = datetime.date.today()
    total_hoy = QuotaUsage.objects.filter(fecha=hoy).aggregate(
        total=models.Sum('unidades')
    )['total'] or 0
    
    if total_hoy > 9000:  # 90% del límite
        logger.warning(f"⚠️ Cuota casi agotada: {total_hoy}/10000")



