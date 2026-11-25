from rest_framework import permissions


class EsPropietarioOSoloLectura(permissions.BasePermission):
    """
    Lectura para todos; escritura solo para el dueño del objeto (o staff).
    Se combina con el permiso global IsAuthenticatedOrReadOnly, no lo reemplaza.
    El ViewSet indica qué campo es el dueño con el atributo `campo_propietario`.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        campo = getattr(view, 'campo_propietario', 'propietario')
        return getattr(obj, campo) == request.user or request.user.is_staff
