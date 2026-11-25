from django.contrib.auth import get_user_model, login, logout
from django.db.models import Count
from django.middleware.csrf import get_token
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import permissions, status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.throttling import ScopedRateThrottle

from .filters import TareaFilter
from .models import Proyecto, Tarea
from .permissions import EsPropietarioOSoloLectura
from .serializers import (
    CambiarEstadoSerializer,
    LoginSerializer,
    ProyectoSerializer,
    RegistroSerializer,
    TareaSerializer,
    UsuarioSerializer,
)


# IA: drf-spectacular "unable to guess serializer" en vistas @api_view → Solución manual:
# las vistas de función no tienen serializer_class; se declara responses=OpenApiTypes.OBJECT.
@extend_schema(summary='Raíz de la API (HATEOAS)', responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def api_root(request, format=None):
    """Punto de entrada: desde aquí el cliente descubre todos los recursos."""
    return Response({
        'proyectos': reverse('proyecto-list', request=request, format=format),
        'tareas': reverse('tarea-list', request=request, format=format),
        'usuarios': reverse('usuario-list', request=request, format=format),
        'csrf': reverse('csrf-token', request=request, format=format),
        'sesion': reverse('auth-me', request=request, format=format),
        'login': reverse('auth-login', request=request, format=format),
        'registro': reverse('auth-registro', request=request, format=format),
        'docs': reverse('swagger-ui', request=request, format=format),
        'schema': reverse('schema', request=request, format=format),
    })


@extend_schema(summary='Obtener token CSRF (SPA con autenticación por sesión)', responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def csrf_token(request):
    """
    El SPA llama a este endpoint al iniciar: get_token() fija la cookie 'csrftoken'.
    Luego envía ese valor en el header X-CSRFToken en cada POST/PUT/PATCH/DELETE.
    No se usa @csrf_exempt: la protección CSRF sigue activa.
    """
    return Response({'csrfToken': get_token(request)})


# ---------------------------------------------------------------------
# Autenticación por sesión para el frontend (SPA servido en el mismo origen)
# ---------------------------------------------------------------------
def _sesion(user):
    if not user or not user.is_authenticated:
        return {'autenticado': False, 'usuario': None}
    return {
        'autenticado': True,
        'usuario': {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'is_staff': user.is_staff,
        },
    }


@extend_schema(summary='Usuario de la sesión actual', responses=OpenApiTypes.OBJECT)
@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def auth_me(request):
    return Response(_sesion(request.user))


@extend_schema(summary='Iniciar sesión', request=LoginSerializer, responses=OpenApiTypes.OBJECT)
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def auth_login(request):
    # SessionAuthentication solo verifica CSRF a usuarios ya autenticados;
    # el login también debe exigirlo (evita "login CSRF").
    SessionAuthentication().enforce_csrf(request)
    serializer = LoginSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data['user']
    login(request._request, user)
    return Response(_sesion(user))


@extend_schema(summary='Crear cuenta e iniciar sesión', request=RegistroSerializer, responses=OpenApiTypes.OBJECT)
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def auth_registro(request):
    SessionAuthentication().enforce_csrf(request)
    serializer = RegistroSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.save()
    login(request._request, user)
    return Response(_sesion(user), status=status.HTTP_201_CREATED)


@extend_schema(summary='Cerrar sesión', request=None, responses=OpenApiTypes.OBJECT)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def auth_logout(request):
    logout(request._request)
    return Response(_sesion(None))


@extend_schema_view(
    list=extend_schema(summary='Listar proyectos'),
    retrieve=extend_schema(summary='Detalle de proyecto'),
    create=extend_schema(summary='Crear proyecto'),
    update=extend_schema(summary='Reemplazar proyecto'),
    partial_update=extend_schema(summary='Actualizar parcialmente un proyecto'),
    destroy=extend_schema(summary='Eliminar proyecto'),
)
class ProyectoViewSet(viewsets.ModelViewSet):
    serializer_class = ProyectoSerializer
    # Permiso global (settings) + regla de propietario a nivel de objeto
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, EsPropietarioOSoloLectura]
    campo_propietario = 'propietario'
    filterset_fields = ['propietario']
    search_fields = ['nombre', 'descripcion']
    ordering_fields = ['nombre', 'created', 'total_tareas']

    def get_queryset(self):
        # QuerySet lazy: el conteo se resuelve en SQL, no en Python
        return (
            Proyecto.objects.select_related('propietario')
            .annotate(total_tareas=Count('tareas'))
            .order_by('-created')
        )

    def perform_create(self, serializer):
        serializer.save(propietario=self.request.user)

    @extend_schema(summary='Estadísticas de tareas por estado del proyecto', responses=OpenApiTypes.OBJECT)
    @action(detail=True, methods=['get'])
    def estadisticas(self, request, pk=None):
        proyecto = self.get_object()
        conteo = proyecto.tareas.values('status').annotate(total=Count('id')).order_by('status')
        return Response({
            'proyecto': proyecto.nombre,
            'por_estado': {fila['status']: fila['total'] for fila in conteo},
        })


@extend_schema_view(
    list=extend_schema(
        summary='Listar tareas (paginado, filtrable, ordenable)',
        parameters=[OpenApiParameter('search', str, description='Busca en título, descripción y proyecto')],
    ),
    retrieve=extend_schema(summary='Detalle de tarea'),
    create=extend_schema(summary='Crear tarea'),
    update=extend_schema(summary='Reemplazar tarea'),
    partial_update=extend_schema(summary='Actualizar parcialmente una tarea'),
    destroy=extend_schema(summary='Eliminar tarea'),
)
class TareaViewSet(viewsets.ModelViewSet):
    serializer_class = TareaSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, EsPropietarioOSoloLectura]
    campo_propietario = 'creado_por'
    filterset_class = TareaFilter
    search_fields = ['titulo', 'descripcion', 'proyecto__nombre']
    ordering_fields = ['created', 'prioridad', 'fecha_limite', 'titulo']
    ordering = ['-created']
    # IA: TypeError "TareaViewSet() received an invalid keyword 'throttle_scope'" al usar
    # @action(throttle_scope=...) → Solución manual: as_view() solo acepta kwargs que ya existen
    # como atributos de la clase; se declara throttle_scope = None y la @action lo sobrescribe.
    throttle_scope = None

    def get_queryset(self):
        return Tarea.objects.select_related('proyecto', 'creado_por')

    def perform_create(self, serializer):
        serializer.save(creado_por=self.request.user)

    def get_throttles(self):
        # La @action cambiar_estado añade un límite propio (scope 'cambio_estado')
        throttles = super().get_throttles()
        if self.action == 'cambiar_estado':
            throttles.append(ScopedRateThrottle())
        return throttles

    @extend_schema(
        summary='Cambiar el estado de una tarea',
        request=CambiarEstadoSerializer,
        responses=TareaSerializer,
    )
    @action(detail=True, methods=['post'], throttle_scope='cambio_estado',
            url_path='cambiar_estado', url_name='cambiar-estado')
    def cambiar_estado(self, request, pk=None):
        tarea = self.get_object()
        entrada = CambiarEstadoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        tarea.status = entrada.validated_data['status']
        tarea.save(update_fields=['status', 'updated'])
        return Response(self.get_serializer(tarea).data, status=status.HTTP_200_OK)

    @extend_schema(summary='Tareas creadas por el usuario autenticado')
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def mias(self, request):
        qs = self.filter_queryset(self.get_queryset().filter(creado_por=request.user))
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)


class UsuarioViewSet(viewsets.ReadOnlyModelViewSet):
    """Solo lectura (GET list / retrieve). No expone datos sensibles."""

    queryset = get_user_model().objects.filter(is_active=True).order_by('id')
    serializer_class = UsuarioSerializer
    search_fields = ['username', 'first_name', 'last_name']
    ordering_fields = ['username', 'id']
