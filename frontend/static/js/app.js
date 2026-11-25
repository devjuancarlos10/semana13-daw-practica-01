/* Orbita – cliente SPA de la API REST (autenticación por sesión + CSRF) */
(() => {
  'use strict';

  const API = '/api';
  const COLORES = ['#5b5bd6', '#1f9d62', '#e0803a', '#d63e4f', '#2f6fde', '#a24fcf', '#0f9aa8', '#c2a40e'];
  const ESTADOS = { pendiente: 'Pendiente', activo: 'En curso', completado: 'Completada' };

  const estado = {
    usuario: null,
    proyectos: [],
    proyectoId: null,        // null = todas
    paginaUrl: null,         // URL absoluta devuelta por la API (next/previous)
    editandoUrl: null,
    filtros: { search: '', status: '', prioridad: '', ordering: '-created', mias: false },
  };

  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

  // ------------------------------------------------------------------ utilidades
  function esc(texto) {
    return String(texto ?? '').replace(/[&<>"']/g, (c) => (
      { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
    ));
  }

  function leerCookie(nombre) {
    const m = document.cookie.match(new RegExp('(?:^|;\\s*)' + nombre + '=([^;]*)'));
    return m ? decodeURIComponent(m[1]) : null;
  }

  function colorProyecto(id) {
    return COLORES[(id - 1) % COLORES.length];
  }

  function formatearFecha(iso) {
    if (!iso) return '';
    const [a, m, d] = iso.split('-').map(Number);
    return new Date(a, m - 1, d).toLocaleDateString('es', { day: 'numeric', month: 'short', year: 'numeric' });
  }

  function toast(mensaje, tipo = '') {
    const el = document.createElement('div');
    el.className = `toast ${tipo}`;
    el.textContent = mensaje;
    $('#toasts').append(el);
    setTimeout(() => el.remove(), 4000);
  }

  function debounce(fn, ms) {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
  }

  // ------------------------------------------------------------------ cliente HTTP
  class ErrorApi extends Error {
    constructor(mensaje, status, datos) { super(mensaje); this.status = status; this.datos = datos; }
  }

  function mensajeDeError(resp, datos) {
    if (resp.status === 429) {
      const s = resp.headers.get('Retry-After');
      return `Demasiadas solicitudes. Intenta de nuevo en ${s || 'unos'} segundos.`;
    }
    if (resp.status === 403) return datos?.detail || 'No tienes permiso para realizar esta acción.';
    if (resp.status === 404) return 'El recurso ya no existe.';
    if (datos?.detail) return datos.detail;
    if (datos?.non_field_errors) return datos.non_field_errors.join(' ');
    if (resp.status === 400) return 'Revisa los datos del formulario.';
    return `Error inesperado (${resp.status}).`;
  }

  async function api(ruta, { method = 'GET', body } = {}) {
    const url = ruta.startsWith('http') ? ruta : API + ruta;
    const headers = { Accept: 'application/json' };
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    // CSRF: obligatorio en métodos no seguros con autenticación por sesión
    if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) headers['X-CSRFToken'] = leerCookie('csrftoken');

    const resp = await fetch(url, {
      method, headers, credentials: 'same-origin',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    let datos = null;
    if (resp.status !== 204) { try { datos = await resp.json(); } catch { /* sin cuerpo */ } }
    if (!resp.ok) throw new ErrorApi(mensajeDeError(resp, datos), resp.status, datos);
    return datos;
  }

  // ------------------------------------------------------------------ errores de formulario
  function limpiarErrores(form) {
    $$('[data-error]', form).forEach((el) => { el.textContent = ''; });
    $$('.invalido', form).forEach((el) => el.classList.remove('invalido'));
  }

  function mostrarErrores(form, err) {
    const datos = err.datos;
    if (err.status === 400 && datos && typeof datos === 'object' && !Array.isArray(datos)) {
      let general = '';
      for (const [campo, msgs] of Object.entries(datos)) {
        const texto = Array.isArray(msgs) ? msgs.join(' ') : String(msgs);
        const destino = $(`[data-error="${campo}"]`, form);
        if (destino) {
          destino.textContent = texto;
          form.elements[campo]?.classList.add('invalido');
        } else {
          general += texto + ' ';
        }
      }
      if (general) $('[data-error="non_field_errors"]', form).textContent = general.trim();
      return;
    }
    $('[data-error="non_field_errors"]', form).textContent = err.message;
  }

  function datosFormulario(form) {
    return Object.fromEntries(new FormData(form).entries());
  }

  async function conBoton(form, fn) {
    const btn = $('button[type="submit"]', form);
    btn.disabled = true;
    try { await fn(); } finally { btn.disabled = false; }
  }

  // ------------------------------------------------------------------ autenticación
  function mostrarVista(autenticado) {
    $('#vista-auth').hidden = autenticado;
    $('#vista-app').hidden = !autenticado;
  }

  async function iniciarSesion(sesion) {
    estado.usuario = sesion.usuario;
    const nombre = estado.usuario.first_name || estado.usuario.username;
    $('#nombre-usuario').textContent = nombre;
    $('#avatar').textContent = nombre.charAt(0).toUpperCase();
    mostrarVista(true);
    await cargarProyectos();
    await refrescar();
  }

  $$('.tab').forEach((tab) => tab.addEventListener('click', () => {
    $$('.tab').forEach((t) => t.classList.toggle('activo', t === tab));
    $('#form-login').hidden = tab.dataset.tab !== 'login';
    $('#form-registro').hidden = tab.dataset.tab !== 'registro';
  }));

  $('#form-login').addEventListener('submit', (e) => {
    e.preventDefault();
    const form = e.currentTarget;
    limpiarErrores(form);
    conBoton(form, async () => {
      try {
        const sesion = await api('/auth/login/', { method: 'POST', body: datosFormulario(form) });
        form.reset();
        await iniciarSesion(sesion);
      } catch (err) { mostrarErrores(form, err); }
    });
  });

  $('#form-registro').addEventListener('submit', (e) => {
    e.preventDefault();
    const form = e.currentTarget;
    limpiarErrores(form);
    conBoton(form, async () => {
      try {
        const sesion = await api('/auth/registro/', { method: 'POST', body: datosFormulario(form) });
        form.reset();
        toast('¡Cuenta creada! Bienvenido a Orbita.', 'ok');
        await iniciarSesion(sesion);
      } catch (err) { mostrarErrores(form, err); }
    });
  });

  $('#btn-logout').addEventListener('click', async () => {
    try { await api('/auth/logout/', { method: 'POST' }); } catch { /* sesión ya cerrada */ }
    estado.usuario = null;
    estado.proyectoId = null;
    mostrarVista(false);
  });

  // ------------------------------------------------------------------ proyectos
  async function cargarProyectos() {
    const todos = [];
    let url = '/proyectos/?ordering=nombre';
    while (url) {                         // recorre todas las páginas
      const pagina = await api(url);
      todos.push(...pagina.results);
      url = pagina.next;
    }
    estado.proyectos = todos;
    pintarProyectos();
  }

  function proyectoActual() {
    return estado.proyectos.find((p) => p.id === estado.proyectoId) || null;
  }

  function pintarProyectos() {
    const total = estado.proyectos.reduce((s, p) => s + p.total_tareas, 0);
    const item = (id, nombre, contador, color) => `
      <button class="proyecto-item ${estado.proyectoId === id ? 'activo' : ''}" data-id="${id ?? ''}">
        <span class="punto" style="background:${color}"></span>
        <span class="nombre">${esc(nombre)}</span>
        <span class="contador">${contador}</span>
      </button>`;
    $('#lista-proyectos').innerHTML =
      item(null, 'Todas las tareas', total, '#9aa0b5') +
      estado.proyectos.map((p) => item(p.id, p.nombre, p.total_tareas, colorProyecto(p.id))).join('');

    // opciones del formulario de tareas (el campo proyecto es un hipervínculo)
    $('#form-tarea').elements.proyecto.innerHTML = estado.proyectos
      .map((p) => `<option value="${esc(p.url)}">${esc(p.nombre)}</option>`).join('');
  }

  $('#lista-proyectos').addEventListener('click', (e) => {
    const btn = e.target.closest('.proyecto-item');
    if (!btn) return;
    estado.proyectoId = btn.dataset.id ? Number(btn.dataset.id) : null;
    estado.paginaUrl = null;
    pintarProyectos();
    refrescar();
  });

  $('#btn-nuevo-proyecto').addEventListener('click', () => {
    const form = $('#form-proyecto');
    form.reset();
    limpiarErrores(form);
    $('#modal-proyecto').showModal();
  });

  $('#form-proyecto').addEventListener('submit', (e) => {
    e.preventDefault();
    const form = e.currentTarget;
    limpiarErrores(form);
    conBoton(form, async () => {
      try {
        const nuevo = await api('/proyectos/', { method: 'POST', body: datosFormulario(form) });
        $('#modal-proyecto').close();
        toast(`Proyecto “${nuevo.nombre}” creado.`, 'ok');
        estado.proyectoId = nuevo.id;
        estado.paginaUrl = null;
        await cargarProyectos();
        await refrescar();
      } catch (err) { mostrarErrores(form, err); }
    });
  });

  $('#btn-eliminar-proyecto').addEventListener('click', async () => {
    const p = proyectoActual();
    if (!p || !confirm(`¿Eliminar el proyecto “${p.nombre}” y todas sus tareas?`)) return;
    try {
      await api(p.url, { method: 'DELETE' });
      toast('Proyecto eliminado.', 'ok');
      estado.proyectoId = null;
      estado.paginaUrl = null;
      await cargarProyectos();
      await refrescar();
    } catch (err) { toast(err.message, 'error'); }
  });

  // ------------------------------------------------------------------ encabezado y estadísticas
  function pintarEncabezado() {
    const p = proyectoActual();
    $('#titulo-vista').textContent = p ? p.nombre : 'Todas las tareas';
    $('#migas').textContent = p ? `Proyecto · creado por ${p.propietario_username}` : 'Espacio de trabajo';
    $('#descripcion-vista').textContent = p ? p.descripcion : '';
    const esDuenio = p && (p.propietario_username === estado.usuario.username || estado.usuario.is_staff);
    $('#btn-eliminar-proyecto').hidden = !esDuenio;
  }

  async function cargarEstadisticas() {
    let conteo = { pendiente: 0, activo: 0, completado: 0 };
    if (estado.proyectoId) {
      const r = await api(`/proyectos/${estado.proyectoId}/estadisticas/`);
      conteo = { ...conteo, ...r.por_estado };
    } else {
      const respuestas = await Promise.all(
        Object.keys(conteo).map((s) => api(`/tareas/?status=${s}`)),
      );
      Object.keys(conteo).forEach((s, i) => { conteo[s] = respuestas[i].count; });
    }
    const total = conteo.pendiente + conteo.activo + conteo.completado;
    const pct = total ? Math.round((conteo.completado / total) * 100) : 0;
    for (const [s, n] of Object.entries(conteo)) $(`[data-stat="${s}"]`).textContent = n;
    $('#stat-pct').textContent = `${pct}%`;
    $('#barra-progreso').style.width = `${pct}%`;
  }

  // ------------------------------------------------------------------ tareas
  function urlTareas() {
    if (estado.paginaUrl) return estado.paginaUrl;
    const f = estado.filtros;
    const params = new URLSearchParams();
    if (estado.proyectoId) params.set('proyecto', estado.proyectoId);
    if (f.search) params.set('search', f.search);
    if (f.status) params.set('status', f.status);
    if (f.prioridad) params.set('prioridad', f.prioridad);
    if (f.ordering) params.set('ordering', f.ordering);
    return `${f.mias ? '/tareas/mias/' : '/tareas/'}?${params}`;
  }

  function puedeEditar(t) {
    return t.creado_por === estado.usuario.username || estado.usuario.is_staff;
  }

  function htmlTarea(t) {
    const editable = puedeEditar(t);
    const opciones = Object.entries(ESTADOS)
      .map(([v, l]) => `<option value="${v}" ${v === t.status ? 'selected' : ''}>${l}</option>`).join('');
    return `
      <article class="tarea ${t.status}" data-id="${t.id}">
        <button class="check" data-accion="completar" ${editable ? '' : 'disabled'}
                title="${t.status === 'completado' ? 'Marcar como pendiente' : 'Marcar como completada'}"
                aria-label="Completar">${t.status === 'completado' ? '✓' : ''}</button>
        <div class="tarea-cuerpo">
          <h3 class="tarea-titulo">${esc(t.titulo)}</h3>
          ${t.descripcion ? `<p class="tarea-desc">${esc(t.descripcion)}</p>` : ''}
          <div class="meta">
            <span class="chip" style="color:${colorProyecto(Number(t.proyecto.match(/(\d+)\/?$/)[1]))}">● ${esc(t.proyecto_nombre)}</span>
            <span class="chip chip-p${t.prioridad}">Prioridad ${esc(t.prioridad_display.toLowerCase())}</span>
            ${t.fecha_limite ? `<span class="chip ${t.vencida ? 'chip-vencida' : ''}">${t.vencida ? 'Vencida · ' : 'Vence '}${formatearFecha(t.fecha_limite)}</span>` : ''}
            <span class="autor">por ${esc(t.creado_por)}</span>
          </div>
        </div>
        <div class="tarea-acciones">
          <select class="estado-select estado-${t.status}" data-accion="estado" aria-label="Estado"
                  ${editable ? '' : 'disabled'}>${opciones}</select>
          ${editable ? `
            <button class="btn-accion" data-accion="editar">Editar</button>
            <button class="btn-accion peligro" data-accion="eliminar">Eliminar</button>` : ''}
        </div>
      </article>`;
  }

  let tareasVisibles = [];

  async function cargarTareas() {
    const lista = $('#lista-tareas');
    lista.innerHTML = '<div class="esqueleto"></div>'.repeat(3);
    const pagina = await api(urlTareas());
    tareasVisibles = pagina.results;

    if (!pagina.results.length) {
      const hayFiltros = Object.entries(estado.filtros).some(([k, v]) => k !== 'ordering' && v);
      lista.innerHTML = `<div class="vacio"><strong>${hayFiltros ? 'Sin resultados' : 'Aún no hay tareas'}</strong>
        ${hayFiltros ? 'Prueba con otros filtros o términos de búsqueda.' : 'Crea la primera con “+ Nueva tarea”.'}</div>`;
    } else {
      lista.innerHTML = pagina.results.map(htmlTarea).join('');
    }

    // paginación
    const tam = 5;
    const actual = estado.paginaUrl ? Number(new URL(estado.paginaUrl).searchParams.get('page') || 1) : 1;
    const totalPaginas = Math.max(1, Math.ceil(pagina.count / tam));
    $('#paginacion').hidden = totalPaginas <= 1;
    $('#pag-info').textContent = `Página ${actual} de ${totalPaginas} · ${pagina.count} tareas`;
    $('#pag-anterior').disabled = !pagina.previous;
    $('#pag-siguiente').disabled = !pagina.next;
    $('#pag-anterior').onclick = () => { estado.paginaUrl = pagina.previous; cargarTareas().catch(fallo); };
    $('#pag-siguiente').onclick = () => { estado.paginaUrl = pagina.next; cargarTareas().catch(fallo); };
  }

  function fallo(err) {
    if (err.status === 403 && !estado.usuario) return;
    toast(err.message, 'error');
  }

  async function refrescar() {
    pintarEncabezado();
    try {
      await Promise.all([cargarTareas(), cargarEstadisticas()]);
    } catch (err) { fallo(err); }
  }

  async function refrescarTodo() {
    await cargarProyectos();
    await refrescar();
  }

  // acciones sobre cada tarea (delegación de eventos)
  $('#lista-tareas').addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-accion]');
    if (!btn || btn.tagName === 'SELECT') return;
    const tarea = tareasVisibles.find((t) => t.id === Number(btn.closest('.tarea').dataset.id));
    if (!tarea) return;

    if (btn.dataset.accion === 'completar') {
      const nuevo = tarea.status === 'completado' ? 'pendiente' : 'completado';
      await cambiarEstado(tarea, nuevo);
    } else if (btn.dataset.accion === 'editar') {
      abrirModalTarea(tarea);
    } else if (btn.dataset.accion === 'eliminar') {
      if (!confirm(`¿Eliminar la tarea “${tarea.titulo}”?`)) return;
      try {
        await api(tarea._links.delete.href, { method: 'DELETE' });
        toast('Tarea eliminada.', 'ok');
        await refrescarTodo();
      } catch (err) { toast(err.message, 'error'); }
    }
  });

  $('#lista-tareas').addEventListener('change', async (e) => {
    if (e.target.dataset.accion !== 'estado') return;
    const tarea = tareasVisibles.find((t) => t.id === Number(e.target.closest('.tarea').dataset.id));
    await cambiarEstado(tarea, e.target.value);
  });

  async function cambiarEstado(tarea, nuevo) {
    try {
      // HATEOAS: la URL de la acción viene en la propia respuesta
      await api(tarea._links.cambiar_estado.href, { method: 'POST', body: { status: nuevo } });
      toast(`“${tarea.titulo}” → ${ESTADOS[nuevo]}`);
      await refrescar();
    } catch (err) {
      toast(err.message, 'error');
      await refrescar();
    }
  }

  // ------------------------------------------------------------------ modal de tarea
  function abrirModalTarea(tarea = null) {
    if (!estado.proyectos.length) {
      toast('Primero crea un proyecto con el botón “+” de la barra lateral.', 'error');
      return;
    }
    const form = $('#form-tarea');
    form.reset();
    limpiarErrores(form);
    estado.editandoUrl = tarea ? tarea.url : null;
    $('#modal-tarea-titulo').textContent = tarea ? 'Editar tarea' : 'Nueva tarea';
    const el = form.elements;
    if (tarea) {
      el.titulo.value = tarea.titulo;
      el.descripcion.value = tarea.descripcion;
      el.proyecto.value = tarea.proyecto;
      el.prioridad.value = tarea.prioridad;
      el.status.value = tarea.status;
      el.fecha_limite.value = tarea.fecha_limite || '';
    } else {
      const p = proyectoActual();
      if (p) el.proyecto.value = p.url;
    }
    $('#modal-tarea').showModal();
    el.titulo.focus();
  }

  $('#btn-nueva-tarea').addEventListener('click', () => abrirModalTarea());

  $('#form-tarea').addEventListener('submit', (e) => {
    e.preventDefault();
    const form = e.currentTarget;
    limpiarErrores(form);
    const datos = datosFormulario(form);
    datos.prioridad = Number(datos.prioridad);
    datos.fecha_limite = datos.fecha_limite || null;
    conBoton(form, async () => {
      try {
        if (estado.editandoUrl) {
          await api(estado.editandoUrl, { method: 'PATCH', body: datos });
          toast('Tarea actualizada.', 'ok');
        } else {
          await api('/tareas/', { method: 'POST', body: datos });
          toast('Tarea creada.', 'ok');
        }
        $('#modal-tarea').close();
        await refrescarTodo();
      } catch (err) { mostrarErrores(form, err); }
    });
  });

  $$('[data-cerrar]').forEach((b) => b.addEventListener('click', () => b.closest('dialog').close()));

  // ------------------------------------------------------------------ filtros
  const aplicarFiltros = () => { estado.paginaUrl = null; cargarTareas().catch(fallo); };
  $('#f-search').addEventListener('input', debounce((e) => { estado.filtros.search = e.target.value.trim(); aplicarFiltros(); }, 350));
  $('#f-status').addEventListener('change', (e) => { estado.filtros.status = e.target.value; aplicarFiltros(); });
  $('#f-prioridad').addEventListener('change', (e) => { estado.filtros.prioridad = e.target.value; aplicarFiltros(); });
  $('#f-ordering').addEventListener('change', (e) => { estado.filtros.ordering = e.target.value; aplicarFiltros(); });
  $('#f-mias').addEventListener('change', (e) => { estado.filtros.mias = e.target.checked; aplicarFiltros(); });

  // ------------------------------------------------------------------ arranque
  (async () => {
    try {
      const sesion = await api('/auth/me/');
      if (sesion.autenticado) await iniciarSesion(sesion);
      else mostrarVista(false);
    } catch (err) {
      mostrarVista(false);
      toast(err.message, 'error');
    }
  })();
})();
