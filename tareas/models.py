from django.conf import settings
from django.db import models


class Proyecto(models.Model):
    nombre = models.CharField(max_length=120, unique=True)
    descripcion = models.TextField(blank=True)
    propietario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='proyectos'
    )
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created']

    def __str__(self):
        return self.nombre


class Tarea(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        ACTIVO = 'activo', 'Activo'
        COMPLETADO = 'completado', 'Completado'

    class Prioridad(models.IntegerChoices):
        BAJA = 1, 'Baja'
        MEDIA = 2, 'Media'
        ALTA = 3, 'Alta'

    titulo = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    # db_index en los campos que más se filtran / ordenan
    status = models.CharField(
        max_length=12, choices=Estado.choices, default=Estado.PENDIENTE, db_index=True
    )
    prioridad = models.PositiveSmallIntegerField(
        choices=Prioridad.choices, default=Prioridad.MEDIA, db_index=True
    )
    fecha_limite = models.DateField(null=True, blank=True)
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE, related_name='tareas')
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tareas'
    )
    created = models.DateTimeField(auto_now_add=True, db_index=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created']
        indexes = [models.Index(fields=['proyecto', 'status'])]

    def __str__(self):
        return f'{self.titulo} [{self.status}]'
