from datetime import date, timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from rest_framework import status
from rest_framework.settings import api_settings
from rest_framework.test import APIClient, APITestCase
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle

from .models import Proyecto, Tarea


class BaseAPITest(APITestCase):
    def setUp(self):
        cache.clear()  # el throttling guarda contadores en caché
        self.ana = User.objects.create_user('ana', password='clave12345')
        self.beto = User.objects.create_user('beto', password='clave12345')
        self.proyecto = Proyecto.objects.create(nombre='Sitio Web', propietario=self.ana)
        manana = date.today() + timedelta(days=1)
        for i in range(7):
            Tarea.objects.create(
                titulo=f'Tarea {i}', proyecto=self.proyecto, creado_por=self.ana,
                status='activo' if i % 2 else 'pendiente', prioridad=(i % 3) + 1,
                fecha_limite=manana,
            )


class SerializacionTests(BaseAPITest):
    def test_hateoas_y_campos_read_only(self):
        r = self.client.get('/api/tareas/')
        tarea = r.data['results'][0]
        self.assertTrue(tarea['url'].startswith('http://testserver/api/tareas/'))
        self.assertTrue(tarea['proyecto'].startswith('http://testserver/api/proyectos/'))
        self.assertIn('cambiar_estado', tarea['_links'])
        self.assertEqual(tarea['creado_por'], 'ana')
        self.assertIn('vencida', tarea)

    def test_usuario_no_expone_campos_sensibles(self):
        r = self.client.get('/api/usuarios/')
        usuario = r.data['results'][0]
        for campo in ('password', 'is_staff', 'is_superuser', 'email'):
            self.assertNotIn(campo, usuario)

    def test_validacion_en_serializador(self):
        self.client.force_authenticate(self.ana)
        url_proy = f'http://testserver/api/proyectos/{self.proyecto.pk}/'
        # prioridad ALTA sin fecha límite -> 400
        r = self.client.post('/api/tareas/', {'titulo': 'Urgente', 'prioridad': 3, 'proyecto': url_proy})
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('fecha_limite', r.data)
        # título muy corto -> 400
        r = self.client.post('/api/tareas/', {'titulo': 'ab', 'proyecto': url_proy})
        self.assertIn('titulo', r.data)
        # fecha pasada -> 400
        ayer = (date.today() - timedelta(days=1)).isoformat()
        r = self.client.post('/api/tareas/', {'titulo': 'Vieja', 'fecha_limite': ayer, 'proyecto': url_proy})
        self.assertIn('fecha_limite', r.data)


class ViewSetRouterTests(BaseAPITest):
    def test_crud_completo(self):
        self.client.force_authenticate(self.ana)
        url_proy = f'http://testserver/api/proyectos/{self.proyecto.pk}/'
        r = self.client.post('/api/tareas/', {'titulo': 'Nueva', 'proyecto': url_proy})
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        detalle = r.data['url']
        self.assertEqual(self.client.patch(detalle, {'status': 'activo'}).data['status'], 'activo')
        self.assertEqual(self.client.delete(detalle).status_code, status.HTTP_204_NO_CONTENT)

    def test_anonimo_solo_lectura(self):
        self.assertEqual(self.client.get('/api/tareas/').status_code, 200)
        r = self.client.post('/api/proyectos/', {'nombre': 'X'})
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_solo_propietario_puede_editar(self):
        self.client.force_authenticate(self.beto)
        r = self.client.patch(f'/api/proyectos/{self.proyecto.pk}/', {'nombre': 'Hack'})
        self.assertEqual(r.status_code, status.HTTP_403_FORBIDDEN)

    def test_actions_personalizadas(self):
        self.client.force_authenticate(self.ana)
        tarea = Tarea.objects.first()
        r = self.client.post(f'/api/tareas/{tarea.pk}/cambiar_estado/', {'status': 'completado'})
        self.assertEqual(r.data['status'], 'completado')
        r = self.client.get(f'/api/proyectos/{self.proyecto.pk}/estadisticas/')
        self.assertEqual(sum(r.data['por_estado'].values()), 7)
        self.assertEqual(self.client.get('/api/tareas/mias/').data['count'], 7)


class FiltradoPaginacionTests(BaseAPITest):
    def test_paginacion(self):
        r = self.client.get('/api/tareas/')
        self.assertEqual(r.data['count'], 7)
        self.assertEqual(len(r.data['results']), 5)
        self.assertIsNotNone(r.data['next'])
        r = self.client.get('/api/tareas/?page=2')
        self.assertEqual(len(r.data['results']), 2)

    def test_filtro_busqueda_ordenamiento(self):
        r = self.client.get('/api/tareas/?status=activo&ordering=-created')
        self.assertEqual(r.data['count'], 3)
        self.assertTrue(all(t['status'] == 'activo' for t in r.data['results']))
        r = self.client.get('/api/tareas/?search=Tarea 4')
        self.assertEqual(r.data['count'], 1)
        r = self.client.get('/api/tareas/?ordering=prioridad')
        prioridades = [t['prioridad'] for t in r.data['results']]
        self.assertEqual(prioridades, sorted(prioridades))
        r = self.client.get('/api/tareas/?prioridad_min=3')
        self.assertTrue(all(t['prioridad'] == 3 for t in r.data['results']))


class ThrottlingTests(BaseAPITest):
    def test_anonimo_recibe_429(self):
        # Tasa reducida solo para la prueba: 3 peticiones/minuto
        tasas = {**api_settings.DEFAULT_THROTTLE_RATES, 'anon': '3/minute'}
        with mock.patch.object(AnonRateThrottle, 'THROTTLE_RATES', tasas):
            codigos = [self.client.get('/api/tareas/').status_code for _ in range(4)]
        self.assertEqual(codigos, [200, 200, 200, 429])

    def test_scope_cambio_estado(self):
        self.client.force_authenticate(self.ana)
        tarea = Tarea.objects.first()
        url = f'/api/tareas/{tarea.pk}/cambiar_estado/'
        tasas = {**api_settings.DEFAULT_THROTTLE_RATES, 'cambio_estado': '2/minute'}
        with mock.patch.object(ScopedRateThrottle, 'THROTTLE_RATES', tasas):
            codigos = [self.client.post(url, {'status': 'activo'}).status_code for _ in range(3)]
        self.assertEqual(codigos, [200, 200, 429])


class CorsCsrfDocsTests(BaseAPITest):
    def test_preflight_cors_origen_permitido(self):
        r = self.client.options(
            '/api/tareas/', HTTP_ORIGIN='http://localhost:5173',
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
        )
        self.assertEqual(r.headers.get('Access-Control-Allow-Origin'), 'http://localhost:5173')
        self.assertEqual(r.headers.get('Access-Control-Allow-Credentials'), 'true')

    def test_cors_origen_no_permitido(self):
        r = self.client.get('/api/tareas/', HTTP_ORIGIN='http://malicioso.com')
        self.assertNotIn('Access-Control-Allow-Origin', r.headers)

    def test_csrf_obligatorio_con_sesion(self):
        cliente = APIClient(enforce_csrf_checks=True)
        cliente.login(username='ana', password='clave12345')
        datos = {'nombre': 'Con CSRF'}
        # Sin header X-CSRFToken -> 403
        self.assertEqual(cliente.post('/api/proyectos/', datos).status_code, 403)
        # Con token obtenido de /api/csrf/ -> 201
        token = cliente.get('/api/csrf/').data['csrfToken']
        r = cliente.post('/api/proyectos/', datos, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)

    def test_documentacion_openapi(self):
        self.assertEqual(self.client.get('/api/docs/').status_code, 200)
        r = self.client.get('/api/schema/')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'openapi: 3', r.content)


class AutenticacionSesionTests(BaseAPITest):
    def test_login_exige_csrf_y_crea_sesion(self):
        cliente = APIClient(enforce_csrf_checks=True)
        datos = {'username': 'ana', 'password': 'clave12345'}
        self.assertEqual(cliente.post('/api/auth/login/', datos).status_code, 403)
        token = cliente.get('/api/csrf/').data['csrfToken']
        r = cliente.post('/api/auth/login/', datos, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(cliente.get('/api/auth/me/').data['usuario']['username'], 'ana')

    def test_login_incorrecto(self):
        r = self.client.post('/api/auth/login/', {'username': 'ana', 'password': 'mala'})
        self.assertEqual(r.status_code, 400)

    def test_registro_valida_password_y_loguea(self):
        r = self.client.post('/api/auth/registro/', {'username': 'nuevo', 'password': '123'})
        self.assertIn('password', r.data)
        r = self.client.post('/api/auth/registro/', {'username': 'nuevo', 'password': 'Orbita!2026x'})
        self.assertEqual(r.status_code, 201)
        self.assertTrue(self.client.get('/api/auth/me/').data['autenticado'])
        self.client.post('/api/auth/logout/')
        self.assertFalse(self.client.get('/api/auth/me/').data['autenticado'])

    def test_frontend_se_sirve_con_cookie_csrf(self):
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        self.assertIn('csrftoken', r.cookies)
        self.assertContains(r, 'Orbita')
