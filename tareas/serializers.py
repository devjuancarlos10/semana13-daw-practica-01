from datetime import date

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.reverse import reverse

from .models import Proyecto, Tarea

User = get_user_model()


class UsuarioSerializer(serializers.HyperlinkedModelSerializer):
    """Solo campos públicos: nunca password, is_staff, is_superuser ni email."""

    url = serializers.HyperlinkedIdentityField(view_name='usuario-detail')

    class Meta:
        model = User
        fields = ('id', 'url', 'username', 'first_name', 'last_name')


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        user = authenticate(
            self.context.get('request'), username=attrs['username'], password=attrs['password']
        )
        if not user:
            raise serializers.ValidationError('Usuario o contraseña incorrectos.')
        attrs['user'] = user
        return attrs


class RegistroSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ('username', 'first_name', 'password')

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class TareaSerializer(serializers.HyperlinkedModelSerializer):
    """
    Pipeline: request.data -> to_internal_value() -> validate_<campo>() -> validate() -> .save()
    HATEOAS: 'url', 'proyecto' y '_links' permiten navegar la API sin documentación externa.
    """

    url = serializers.HyperlinkedIdentityField(view_name='tarea-detail')
    proyecto = serializers.HyperlinkedRelatedField(
        view_name='proyecto-detail', queryset=Proyecto.objects.all()
    )
    # Campos de solo lectura
    creado_por = serializers.ReadOnlyField(source='creado_por.username')
    proyecto_nombre = serializers.ReadOnlyField(source='proyecto.nombre')
    prioridad_display = serializers.CharField(source='get_prioridad_display', read_only=True)
    vencida = serializers.SerializerMethodField()
    _links = serializers.SerializerMethodField()

    class Meta:
        model = Tarea
        fields = (
            'id', 'url', 'titulo', 'descripcion', 'status', 'prioridad', 'prioridad_display',
            'fecha_limite', 'vencida', 'proyecto', 'proyecto_nombre', 'creado_por',
            'created', 'updated', '_links',
        )
        read_only_fields = ('created', 'updated')

    def get_vencida(self, obj) -> bool:
        return bool(
            obj.fecha_limite
            and obj.fecha_limite < date.today()
            and obj.status != Tarea.Estado.COMPLETADO
        )

    def get__links(self, obj) -> dict:
        request = self.context.get('request')
        detalle = reverse('tarea-detail', args=[obj.pk], request=request)
        return {
            'self': {'href': detalle, 'method': 'GET'},
            'update': {'href': detalle, 'method': 'PUT'},
            'delete': {'href': detalle, 'method': 'DELETE'},
            'cambiar_estado': {
                'href': reverse('tarea-cambiar-estado', args=[obj.pk], request=request),
                'method': 'POST',
            },
            'proyecto': {
                'href': reverse('proyecto-detail', args=[obj.proyecto_id], request=request),
                'method': 'GET',
            },
        }

    # --- Validación por campo ---
    def validate_titulo(self, value):
        value = value.strip()
        if len(value) < 3:
            raise serializers.ValidationError('El título debe tener al menos 3 caracteres.')
        return value

    # --- Validación de objeto (reglas que combinan varios campos) ---
    def validate(self, attrs):
        inst = self.instance
        fecha_limite = attrs.get('fecha_limite', getattr(inst, 'fecha_limite', None))
        estado = attrs.get('status', getattr(inst, 'status', Tarea.Estado.PENDIENTE))
        prioridad = attrs.get('prioridad', getattr(inst, 'prioridad', Tarea.Prioridad.MEDIA))

        if fecha_limite and fecha_limite < date.today() and estado != Tarea.Estado.COMPLETADO:
            raise serializers.ValidationError(
                {'fecha_limite': 'No puede ser una fecha pasada si la tarea no está completada.'}
            )
        if prioridad == Tarea.Prioridad.ALTA and not fecha_limite:
            raise serializers.ValidationError(
                {'fecha_limite': 'Las tareas de prioridad ALTA requieren fecha límite.'}
            )
        return attrs


class CambiarEstadoSerializer(serializers.Serializer):
    """Entrada de la @action personalizada POST /api/tareas/{id}/cambiar_estado/."""

    status = serializers.ChoiceField(choices=Tarea.Estado.choices)


class ProyectoSerializer(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(view_name='proyecto-detail')
    propietario = serializers.HyperlinkedRelatedField(view_name='usuario-detail', read_only=True)
    propietario_username = serializers.ReadOnlyField(source='propietario.username')
    total_tareas = serializers.IntegerField(read_only=True)  # viene de .annotate() en el ViewSet
    tareas_url = serializers.SerializerMethodField()

    class Meta:
        model = Proyecto
        fields = (
            'id', 'url', 'nombre', 'descripcion', 'propietario', 'propietario_username',
            'total_tareas', 'tareas_url', 'created',
        )
        read_only_fields = ('created',)

    def get_tareas_url(self, obj) -> str:
        """HATEOAS: enlace a las tareas de este proyecto (filtro por query param)."""
        base = reverse('tarea-list', request=self.context.get('request'))
        return f'{base}?proyecto={obj.pk}'

    def validate_nombre(self, value):
        value = value.strip()
        qs = Proyecto.objects.filter(nombre__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('Ya existe un proyecto con ese nombre.')
        return value
