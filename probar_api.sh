#!/usr/bin/env bash
# Batería de pruebas HTTP de la API (equivalente a api.http)
B=http://127.0.0.1:8000/api
P=$B/proyectos/1/
prueba(){ desc="$1"; esp="$2"; shift 2; code=$(curl -s -o /dev/null -w "%{http_code}" "$@"); [ "$code" = "$esp" ] && r="OK   " || r="FALLA"; printf "%s  esperado %s  obtenido %s   %s
" "$r" "$esp" "$code" "$desc"; }
J='-H Content-Type:application/json'
prueba "GET  /api/ (raíz HATEOAS)"                 200 $B/
prueba "GET  /api/tareas/?status=activo&page=1"    200 "$B/tareas/?status=activo&page=1"
prueba "GET  /api/tareas/?search=pagos"            200 "$B/tareas/?search=pagos"
prueba "POST /api/tareas/ sin autenticación"       403 -X POST $J -d "{\"titulo\":\"x\"}" $B/tareas/
prueba "POST /api/tareas/ autenticado"             201 -u ana:clave12345 -X POST $J -d "{\"titulo\":\"Revisar contrato\",\"proyecto\":\"$P\"}" $B/tareas/
prueba "POST prioridad alta sin fecha límite"      400 -u ana:clave12345 -X POST $J -d "{\"titulo\":\"Urgente\",\"prioridad\":3,\"proyecto\":\"$P\"}" $B/tareas/
prueba "PATCH /api/tareas/2/ (partial_update)"     200 -u ana:clave12345 -X PATCH $J -d "{\"status\":\"activo\"}" $B/tareas/2/
prueba "PATCH proyecto de otro usuario"            403 -u ana:clave12345 -X PATCH $J -d "{\"nombre\":\"x\"}" $B/proyectos/3/
prueba "POST /api/tareas/2/cambiar_estado/"        200 -u ana:clave12345 -X POST $J -d "{\"status\":\"activo\"}" $B/tareas/2/cambiar_estado/
prueba "GET  /api/tareas/mias/"                    200 -u ana:clave12345 $B/tareas/mias/
prueba "GET  /api/proyectos/1/estadisticas/"       200 $B/proyectos/1/estadisticas/
prueba "OPTIONS preflight desde localhost:5173"    200 -X OPTIONS -H "Origin: http://localhost:5173" -H "Access-Control-Request-Method: POST" $B/tareas/
prueba "GET  /api/docs/ (Swagger UI)"              200 $B/docs/
