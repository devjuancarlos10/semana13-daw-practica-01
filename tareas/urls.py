from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

# El router genera las rutas automáticamente:
#   /tareas/        GET -> list,     POST -> create
#   /tareas/{pk}/   GET -> retrieve, PUT -> update, PATCH -> partial_update, DELETE -> destroy
#   /tareas/{pk}/cambiar_estado/   (@action detail=True)
#   /tareas/mias/                  (@action detail=False)
router = DefaultRouter()
router.include_root_view = False  # usamos nuestra propia raíz HATEOAS (views.api_root)
router.register(r'proyectos', views.ProyectoViewSet, basename='proyecto')
router.register(r'tareas', views.TareaViewSet, basename='tarea')
router.register(r'usuarios', views.UsuarioViewSet, basename='usuario')

urlpatterns = [
    path('', views.api_root, name='api-root'),
    path('csrf/', views.csrf_token, name='csrf-token'),
    path('auth/me/', views.auth_me, name='auth-me'),
    path('auth/login/', views.auth_login, name='auth-login'),
    path('auth/registro/', views.auth_registro, name='auth-registro'),
    path('auth/logout/', views.auth_logout, name='auth-logout'),
    path('', include(router.urls)),
]
