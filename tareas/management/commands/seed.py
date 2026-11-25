from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from tareas.models import Proyecto, Tarea


class Command(BaseCommand):
    help = 'Crea usuarios, proyectos y tareas de ejemplo para probar la API.'

    def handle(self, *args, **options):
        admin, _ = User.objects.get_or_create(username='admin', defaults={'is_staff': True, 'is_superuser': True})
        admin.set_password('admin12345')
        admin.save()
        ana, _ = User.objects.get_or_create(username='ana', defaults={'first_name': 'Ana'})
        ana.set_password('clave12345')
        ana.save()
        carlos, _ = User.objects.get_or_create(username='carlos', defaults={'first_name': 'Carlos'})
        carlos.set_password('clave12345')
        carlos.save()

        datos = {
            'Lanzamiento App Móvil': ['Diseñar pantalla de bienvenida', 'Integrar pasarela de pagos',
                                      'Pruebas en dispositivos Android', 'Publicar en tiendas',
                                      'Campaña de lanzamiento', 'Recoger feedback de usuarios'],
            'Rediseño de Marca': ['Nuevo logotipo', 'Paleta de colores', 'Guía de estilo',
                                  'Actualizar redes sociales'],
            'Mudanza de Oficina': ['Cotizar empresas de mudanza', 'Inventario de equipos',
                                   'Contratar internet'],
        }
        estados = ['pendiente', 'activo', 'completado']
        i = 0
        for nombre, tareas in datos.items():
            duenio = carlos if nombre == 'Mudanza de Oficina' else ana
            proyecto, _ = Proyecto.objects.get_or_create(nombre=nombre, defaults={'propietario': duenio})
            for titulo in tareas:
                Tarea.objects.get_or_create(
                    titulo=titulo, proyecto=proyecto,
                    defaults={
                        'creado_por': duenio,
                        'status': estados[i % 3],
                        'prioridad': (i % 3) + 1,
                        'fecha_limite': date.today() + timedelta(days=i + 1),
                    },
                )
                i += 1
        self.stdout.write(self.style.SUCCESS(
            f'OK: {Proyecto.objects.count()} proyectos, {Tarea.objects.count()} tareas. '
            'Usuarios: ana, carlos (clave12345) y admin (admin12345)'
        ))
