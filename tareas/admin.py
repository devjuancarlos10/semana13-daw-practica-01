from django.contrib import admin

from .models import Proyecto, Tarea


@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'propietario', 'created')
    search_fields = ('nombre',)


@admin.register(Tarea)
class TareaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'proyecto', 'status', 'prioridad', 'fecha_limite', 'creado_por')
    list_filter = ('status', 'prioridad', 'proyecto')
    search_fields = ('titulo',)
