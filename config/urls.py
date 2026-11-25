from django.contrib import admin
from django.urls import include, path
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import TemplateView
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    # Frontend (SPA). ensure_csrf_cookie deja la cookie 'csrftoken' lista para el JS.
    path('', ensure_csrf_cookie(TemplateView.as_view(template_name='index.html')), name='home'),
    path('admin/', admin.site.urls),
    path('api/', include('tareas.urls')),
    # Login / logout para la Browsable API (SessionAuthentication)
    path('api-auth/', include('rest_framework.urls')),
    # Documentación OpenAPI 3 (drf-spectacular)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
