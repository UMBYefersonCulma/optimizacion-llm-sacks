/* Frases de Sacks · pantalla única.
   Todo debe caber en la ventana sin desplazarse: las secciones largas se dividen en pestañas y las listas
   se paginan según el alto disponible (cambia con el tamaño de la ventana y con el tamaño de texto). */
(function () {
  'use strict';

  function lista(raiz, sel) { return Array.prototype.slice.call(raiz.querySelectorAll(sel)); }
  // Cambios hechos por la persona (página o pestaña); lectura.js los anuncia en voz alta.
  function avisar(nombre, detalle) { try { window.dispatchEvent(new CustomEvent(nombre, { detail: detalle })); } catch (e) { /* navegador antiguo */ } }

  // ── Paginación ajustada al alto ──
  function crearNav(caja) {
    var nav = document.createElement('nav');
    nav.className = 'paginador';
    nav.setAttribute('aria-label', caja.getAttribute('data-paginar') || 'Páginas');
    nav.innerHTML = '<button type="button" class="chip pag-ant">‹ Anterior</button>' +
      '<span class="pag-estado" aria-live="polite"></span>' +
      '<button type="button" class="chip pag-sig">Siguiente ›</button>';
    caja.appendChild(nav);
    nav.querySelector('.pag-ant').addEventListener('click', function () { mostrar(caja, (caja._pagina || 0) - 1); avisar('sacks:pagina', { caja: caja }); });
    nav.querySelector('.pag-sig').addEventListener('click', function () { mostrar(caja, (caja._pagina || 0) + 1); avisar('sacks:pagina', { caja: caja }); });
    return nav;
  }

  function mostrar(caja, n) {
    var paginas = caja._paginas || [];
    if (!paginas.length) return;
    n = Math.max(0, Math.min(paginas.length - 1, n));
    caja._pagina = n;
    paginas.forEach(function (p, i) { p.forEach(function (it) { it.hidden = i !== n; }); });
    var nav = caja.querySelector('.paginador');
    nav.hidden = paginas.length < 2;
    nav.querySelector('.pag-estado').textContent = 'Página ' + (n + 1) + ' de ' + paginas.length;
    nav.querySelector('.pag-ant').disabled = n === 0;
    nav.querySelector('.pag-sig').disabled = n === paginas.length - 1;
  }

  function paginar(caja) {
    var cont = caja.querySelector('[data-items]') || caja.querySelector('tbody');
    if (!cont) return;
    var items = Array.prototype.slice.call(cont.children);
    var nav = caja.querySelector('.paginador') || crearNav(caja);
    items.forEach(function (it) { it.hidden = false; });
    nav.hidden = false;
    caja.style.minHeight = '';
    if (!caja.offsetParent || !items.length) return;           // pestaña oculta: se pagina al mostrarla
    var thead = caja.querySelector('thead');
    var extra = nav.offsetHeight + 6 + (thead ? thead.offsetHeight : 0);
    var disponible = caja.clientHeight - extra;
    // Nunca se recorta un elemento: si uno solo no cabe (texto ampliado, pantallas pequeñas), la caja crece lo justo
    // para mostrarlo completo y el área central se desplaza esa diferencia.
    var maximo = items.reduce(function (m, it) { return Math.max(m, it.offsetHeight); }, 0);
    if (maximo > disponible) { caja.style.minHeight = (maximo + extra) + 'px'; disponible = maximo; }
    var paginas = [], actual = [], inicio = null;
    items.forEach(function (it) {
      var arriba = it.offsetTop, abajo = arriba + it.offsetHeight;
      if (inicio === null) inicio = arriba;
      if (actual.length && abajo - inicio > disponible) { paginas.push(actual); actual = []; inicio = arriba; }
      actual.push(it);
    });
    if (actual.length) paginas.push(actual);
    caja._paginas = paginas;
    mostrar(caja, caja._pagina || 0);
  }

  function paginarTodo() { lista(document, '[data-paginar]').forEach(paginar); }
  window.sacksPaginar = paginarTodo;

  // ── Pestañas accesibles (flechas, Inicio, Fin) ──
  function iniciarPestanas(grupo) {
    var tabs = lista(grupo, '[role="tab"]');
    var clave = 'pestana:' + location.pathname;
    function activar(tab, enfocar, usuario) {
      tabs.forEach(function (t) {
        var sel = t === tab;
        t.setAttribute('aria-selected', sel ? 'true' : 'false');
        t.tabIndex = sel ? 0 : -1;
        var p = document.getElementById(t.getAttribute('aria-controls'));
        if (p) p.hidden = !sel;
      });
      if (enfocar) tab.focus();
      var panel = document.getElementById(tab.getAttribute('aria-controls'));
      if (panel) lista(panel, '[data-paginar]').forEach(paginar);
      try { sessionStorage.setItem(clave, tab.id); } catch (e) { /* sin almacenamiento */ }
      var h = tab.getAttribute('data-hash');
      if (h && location.hash !== '#' + h && window.history && history.replaceState) history.replaceState(null, '', '#' + h);
      if (usuario) avisar('sacks:pestana', { tab: tab, panel: panel });
    }
    function porHash() {
      var h = (location.hash || '').slice(1);
      return h ? tabs.filter(function (t) { return t.getAttribute('data-hash') === h; })[0] : null;
    }
    window.addEventListener('hashchange', function () { var t = porHash(); if (t) activar(t); });
    tabs.forEach(function (t, i) {
      t.addEventListener('click', function () { activar(t, false, true); });
      t.addEventListener('keydown', function (e) {
        var j = null;
        if (e.key === 'ArrowRight') j = (i + 1) % tabs.length;
        else if (e.key === 'ArrowLeft') j = (i - 1 + tabs.length) % tabs.length;
        else if (e.key === 'Home') j = 0;
        else if (e.key === 'End') j = tabs.length - 1;
        if (j !== null) { e.preventDefault(); activar(tabs[j], true, true); }
      });
    });
    var guardada = null;
    try { guardada = sessionStorage.getItem(clave); } catch (e) { /* sin almacenamiento */ }
    var inicial = porHash() || (guardada && document.getElementById(guardada)) || tabs[0];
    if (inicial && tabs.indexOf(inicial) >= 0) activar(inicial); else if (tabs[0]) activar(tabs[0]);
  }

  var espera = null;
  function repaginar() { clearTimeout(espera); espera = setTimeout(paginarTodo, 120); }

  document.addEventListener('DOMContentLoaded', function () {
    lista(document, '[role="tablist"]').forEach(iniciarPestanas);
    paginarTodo();
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(paginarTodo);
  });
  window.addEventListener('resize', repaginar);
  window.addEventListener('sacks:diseno', repaginar);   // cambios de tamaño de texto o tipografía (panel de accesibilidad)
})();
