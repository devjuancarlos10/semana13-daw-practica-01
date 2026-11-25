import django_filters

from .models import Tarea


class TareaFilter(django_filters.FilterSet):
    """Filtros por query params, ej.: ?status=activo&prioridad_min=2&creado_desde=2026-01-01"""

    titulo = django_filters.CharFilter(lookup_expr='icontains')
    prioridad_min = django_filters.NumberFilter(field_name='prioridad', lookup_expr='gte')
    creado_desde = django_filters.DateFilter(field_name='created', lookup_expr='date__gte')
    creado_hasta = django_filters.DateFilter(field_name='created', lookup_expr='date__lte')
    vence_antes = django_filters.DateFilter(field_name='fecha_limite', lookup_expr='lte')

    class Meta:
        model = Tarea
        fields = ['status', 'prioridad', 'proyecto']
