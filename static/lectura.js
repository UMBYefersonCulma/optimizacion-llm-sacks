/* Frases de Sacks · lectura en voz alta de toda la aplicación.
   Con «Leer en voz alta» activo (panel de accesibilidad):
   · cada pantalla se lee al abrirse: los elementos marcados con data-leer, en orden (data-leer-texto reemplaza el texto);
   · se lee lo que se enfoca con Tab o con las flechas, y el estado de casillas, opciones y listas al cambiarlas;
   · se leen los avisos y errores (role="alert"), los mensajes de validación, las ventanas de ayuda al abrirse
     y los cambios de pestaña o de página;
   · cualquier texto al que se le hace clic se lee (en las tablas, la fila completa con sus encabezados).
   El botón «Escuchar» de la barra superior (o Alt + L) lee la pantalla otra vez o detiene la voz.
   La voz la pone a11y.js (window.sacksHablar). */
(function () {
  'use strict';

  function activa() { return !!(window.sacksVozActiva && window.sacksVozActiva()); }
  function hablar(texto, forzar, encolar) { if (texto && window.sacksHablar) window.sacksHablar(texto, forzar, encolar); }
  function lista(raiz, sel) { return Array.prototype.slice.call(raiz.querySelectorAll(sel)); }
  function visible(el) { return !!el && el.getClientRects().length > 0 && !el.closest('[aria-hidden="true"]'); }

  // ── texto que suena bien ──
  var MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  function limpiar(t) {
    return String(t || '')
      .replace(/[→←›‹✓✗✕🔊▶■«»"“”]/g, ' ')
      .replace(/\b(\d{1,2})\/(\d{1,2})\/(\d{4})\b/g, function (m, d, mes, a) { return +d + ' de ' + (MESES[+mes - 1] || mes) + ' de ' + a; })
      .replace(/\b(\d{1,2}):(\d{2})\b/g, function (m, h, mi) { return +h + (mi === '00' ? ' en punto' : ' y ' + +mi); })
      .replace(/_\d{8}_\d{6}/g, '')
      .replace(/\.csv\b/gi, '')
      .replace(/_/g, ' ')
      .replace(/(\d)\.(\d)/g, '$1,$2')
      .replace(/(\d),0(?!\d)/g, '$1')
      .replace(/\s?%/g, ' por ciento')
      .replace(/(\d) s\b/g, '$1 segundos')
      .replace(/\s+\\\s+/g, ' frente a ')
      .replace(/\s*·\s*/g, ', ')
      .replace(/(^|\s)—(?=\s|,|$)/g, '$1sin dato')
      .replace(/\b[IVX]{1,5}\.\s+(?=[A-ZÁÉÍÓÚ])/g, '')
      .replace(/\b[A-ZÁÉÍÓÚÑ]{4,}\b/g, function (m) { return m.toLowerCase(); })
      .replace(/\bIA\b/g, 'I A')
      .replace(/\bEj\.:?/g, 'Por ejemplo')
      .replace(/\s*\n+\s*/g, '. ')
      .replace(/\s+/g, ' ')
      .replace(/\s+([.,;:])/g, '$1')
      .replace(/…\s*[.,]/g, '…')
      .replace(/([.,;:])(\s*[.,;:])+/g, '$1')
      .replace(/^[\s.,;:]+/, '')
      .trim();
  }
  function cerrarFrase(t) { return t && !/[.!?…:]$/.test(t) ? t + '.' : t; }

  function textoDe(el) {
    if (!el) return '';
    if (el.hasAttribute('data-leer-texto')) return el.getAttribute('data-leer-texto');
    var rol = el.getAttribute('role');
    if (rol === 'tablist') {
      var tabs = lista(el, '[role="tab"]');
      var abierta = tabs.filter(function (t) { return t.getAttribute('aria-selected') === 'true'; })[0];
      return 'Pestañas: ' + tabs.map(function (t) { return limpiar(t.innerText); }).join(', ') + '.' +
        (abierta ? ' Abierta: ' + limpiar(abierta.innerText) + '.' : '');
    }
    if (rol === 'img') return el.getAttribute('aria-label') || '';
    return getComputedStyle(el).textTransform === 'uppercase' ? el.textContent : el.innerText;   // sin MAYÚSCULAS de estilo
  }

  // ── la pantalla completa ──
  function textoPagina() {
    var raiz = document.getElementById('contenido') || document.body;
    var marcados = lista(raiz, '[data-leer]').filter(function (el) { return visible(el) && !el.closest('dialog'); });
    if (!marcados.length) marcados = lista(raiz, 'h1, h2, .intro, .meta').filter(visible).slice(0, 3);
    return marcados.map(function (el) { return cerrarFrase(limpiar(textoDe(el))); }).filter(Boolean).join(' ');
  }
  window.sacksLeerPagina = textoPagina;

  // ── nombre y estado de un control (lo que se enfoca o cambia) ──
  function textoIds(ids) {
    return (ids || '').split(/\s+/).map(function (id) { var x = id && document.getElementById(id); return x ? x.innerText : ''; }).join(' ');
  }
  function nombreDe(el) {
    var n = el.getAttribute('aria-label') || textoIds(el.getAttribute('aria-labelledby'));
    if (!n && el.labels && el.labels.length) n = el.type === 'file' ? el.labels[0].innerText   // el otro es el botón «Elegir archivo»
      : Array.prototype.map.call(el.labels, function (l) { return l.innerText; }).join(' ');
    if (!n && el.tagName === 'INPUT' && /^(submit|button)$/i.test(el.type)) n = el.value;
    if (!n && el.getAttribute('role') !== 'tabpanel') n = el.innerText;
    if (!n) n = el.getAttribute('title') || el.getAttribute('placeholder') || '';
    return limpiar(n);
  }
  function describir(el) {
    var nombre = nombreDe(el).replace(/[.:]+$/, ''), partes = [nombre];
    var tag = el.tagName, tipo = (el.getAttribute('type') || '').toLowerCase(), rol = el.getAttribute('role');
    if (rol === 'tab') partes.push('pestaña' + (el.getAttribute('aria-selected') === 'true' ? ', abierta' : ''));
    else if (rol === 'tabpanel') partes.push('contenido de la pestaña');
    else if (rol === 'switch') partes.push('interruptor, ' + (el.checked ? 'activado' : 'desactivado'));
    else if (tipo === 'checkbox') partes.push('casilla, ' + (el.checked ? 'marcada' : 'sin marcar'));
    else if (tipo === 'radio') partes.push('opción' + (el.checked ? ', elegida' : ''));
    else if (tag === 'SELECT') partes.push('lista para elegir, ' + (el.value ? 'elegido: ' + el.options[el.selectedIndex].text : 'sin elegir'));
    else if (tipo === 'file') partes.push('elegir archivo, ' + (el.files && el.files.length ? 'elegido: ' + el.files[0].name : 'ninguno elegido'));
    else if (tipo === 'range') partes.push('control deslizante, ' + el.value);
    else if (tag === 'TEXTAREA' || (tag === 'INPUT' && /^(text|number|search|email|tel|)$/.test(tipo)))
      partes.push((tipo === 'number' ? 'campo de número' : 'campo de texto') + (el.value ? ', escrito: ' + el.value : ', vacío'));
    else if (tag === 'A') partes.push(el.getAttribute('aria-current') === 'page' ? 'enlace, vista actual' : 'enlace');
    else if (tag === 'BUTTON' || tipo === 'submit' || rol === 'button') partes.push('botón');
    if (el.getAttribute('aria-current') === 'true') partes.push('actual');
    if (el.getAttribute('aria-expanded') === 'true') partes.push('abierto');
    if (el.disabled || el.getAttribute('aria-disabled') === 'true') partes.push('todavía no disponible');
    var desc = limpiar(textoIds(el.getAttribute('aria-describedby')));
    if (desc && nombre.indexOf(desc) < 0) partes.push(desc);
    return cerrarFrase(limpiar(partes.filter(Boolean).join(', ')));
  }

  // ── bloques de texto (clic para escuchar) ──
  var LEIBLE = 'h1, h2, h3, h4, p, li, dt, dd, td, th, legend, blockquote, .kpi, .alerta, [role="img"]';
  var NO_LEER = 'a, button, input, select, textarea, label, summary, [role="tab"], [role="button"], .topbar, .panel-a11y, [data-voz="no"]';
  function fila(tr) {
    var tabla = tr.closest('table');
    var cab = tabla && tabla.tHead && tabla.tHead.rows[0] ? Array.prototype.slice.call(tabla.tHead.rows[0].cells) : [];
    var celdas = Array.prototype.slice.call(tr.cells);
    if (tabla.classList.contains('matriz')) {                       // matriz de confusión
      return 'El psicólogo dijo ' + limpiar(celdas[0].innerText) + '; la I A dijo: ' + celdas.slice(1).map(function (c, i) {
        var n = limpiar(c.innerText); return limpiar(cab[i + 1].innerText) + ', ' + (n === '0' ? 'ninguna vez' : n + (n === '1' ? ' vez' : ' veces'));
      }).join('; ') + '.';
    }
    return celdas.filter(visible).map(function (c) {
      var i = celdas.indexOf(c), v = limpiar(c.innerText).replace(/[.]+$/, '') || 'sin dato', h = cab[i] ? limpiar(cab[i].innerText) : '';
      if (h === '#') return 'Número ' + v;
      if (h === 'Coincide') return v ? (c.querySelector('.ok') ? 'Coincide' : 'No coincide') : '';
      return h ? h + ': ' + v : v;
    }).filter(Boolean).join('. ') + '.';
  }
  function textoBloque(b) {
    var tr = b.closest('tbody tr');
    if (tr) return fila(tr);
    var par = b.closest('.faq > div');
    if (par) return lista(par, 'dt, dd').map(function (x) { return cerrarFrase(limpiar(x.innerText)); }).join(' ');
    return cerrarFrase(limpiar(textoDe(b)));
  }

  function textoDialogo(d) {
    var partes = [];
    var titulo = d.querySelector('h2, h3');
    if (titulo) partes.push(cerrarFrase(limpiar(titulo.innerText)));
    lista(d, '.faq > div').filter(visible).forEach(function (x) { partes.push(textoBloque(x.querySelector('dt'))); });
    var pag = d.querySelector('.paginador:not([hidden]) .pag-estado');
    if (pag && pag.textContent) partes.push(pag.textContent + '. Hay más preguntas en la página siguiente.');
    return partes.join(' ');
  }

  // ── eventos ──
  var navTeclado = 0;
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Tab' || /^Arrow/.test(e.key) || e.key === 'Home' || e.key === 'End') navTeclado = Date.now();
    if (e.altKey && e.code === 'KeyL' && !e.ctrlKey && !e.metaKey) { e.preventDefault(); alternar(); }
  }, true);

  // Lo que se enfoca con el teclado (si llega justo después de la lectura de la pantalla, se lee a continuación).
  document.addEventListener('focusin', function (e) {
    if (!activa() || Date.now() - navTeclado > 400) return;
    var el = e.target;
    if (!el.closest || el.closest('[data-voz="no"]') || el === document.body) return;
    hablar(describir(el), false, window.sacksVozReciente && window.sacksVozReciente());
  });

  // Casillas, opciones, listas y archivos: se confirma lo elegido.
  document.addEventListener('change', function (e) {
    var el = e.target;
    if (!activa() || el.id === 'a11y-voz' || (el.closest && el.closest('[data-voz="no"]'))) return;
    var tipo = (el.getAttribute('type') || '').toLowerCase();
    if (tipo === 'checkbox' || tipo === 'radio' || tipo === 'file' || el.tagName === 'SELECT') hablar(describir(el));
  });

  // Clic en un texto: se lee ese bloque (o lo que esté seleccionado).
  document.addEventListener('click', function (e) {
    if (!activa() || e.defaultPrevented || !e.target.closest) return;
    var t = e.target;
    if (t.closest(NO_LEER)) return;
    var sel = window.getSelection ? String(window.getSelection()).trim() : '';
    if (sel.length > 2) { hablar(limpiar(sel)); return; }
    var bloque = t.closest(LEIBLE);
    if (!bloque || !visible(bloque) || !bloque.closest('#contenido, dialog')) return;
    hablar(textoBloque(bloque));
  });

  // Mensajes de validación del navegador (campo vacío, casilla sin marcar…): solo el primero de cada envío.
  var avisoValidacion = null;
  document.addEventListener('invalid', function (e) {
    if (!activa() || avisoValidacion) return;
    var el = e.target;
    avisoValidacion = setTimeout(function () { avisoValidacion = null; hablar(cerrarFrase(limpiar(nombreDe(el).replace(/[.:]+$/, '') + '. ' + el.validationMessage))); }, 0);
  }, true);

  // Pestañas y páginas cambiadas por la persona.
  window.addEventListener('sacks:pestana', function (e) {
    if (!activa()) return;
    var panel = e.detail.panel, partes = ['Pestaña ' + limpiar(e.detail.tab.innerText) + '.'];
    if (panel) {
      var marcados = lista(panel, '[data-leer]').filter(visible);
      if (!marcados.length) marcados = lista(panel, '.meta, h3').filter(visible).slice(0, 1);
      marcados.forEach(function (el) { partes.push(cerrarFrase(limpiar(textoDe(el)))); });
    }
    hablar(partes.join(' '));
  });
  window.addEventListener('sacks:pagina', function (e) {
    if (!activa()) return;
    var caja = e.detail.caja, estado = caja.querySelector('.pag-estado'), texto = estado ? estado.textContent + '.' : '';
    var dialogo = caja.closest('dialog');
    if (dialogo) texto += ' ' + lista(caja, '.faq > div').filter(visible).map(function (x) { return textoBloque(x.querySelector('dt')); }).join(' ');
    else if (caja.querySelector('tbody')) texto += ' Haz clic en una fila para escucharla.';
    hablar(texto);
  });

  function observar() {
    // Ventanas de ayuda: se leen al abrirse; al cerrarse se calla la voz.
    lista(document, 'dialog').forEach(function (d) {
      new MutationObserver(function () {
        if (!activa()) return;
        if (d.open) hablar(textoDialogo(d)); else if (window.sacksCallar) window.sacksCallar();
      }).observe(d, { attributes: true, attributeFilter: ['open'] });
    });
    // Avisos y errores que aparecen o cambian (role="alert").
    new MutationObserver(function (cambios) {
      if (!activa()) return;
      var alertas = [];
      cambios.forEach(function (m) {
        var el = m.target.nodeType === 1 ? m.target : m.target.parentElement;
        var a = el && el.closest && el.closest('[role="alert"]');
        if (a && alertas.indexOf(a) < 0 && visible(a) && !a.closest('[data-voz="no"]')) alertas.push(a);
      });
      alertas.forEach(function (a) { hablar(cerrarFrase(limpiar(a.innerText))); });
    }).observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['hidden'] });
  }

  // ── botón «Escuchar» de la barra superior ──
  var boton = null;
  function alternar() {
    if (window.sacksVozHablando && window.sacksVozHablando()) window.sacksCallar();
    else hablar(textoPagina(), true);
  }
  function pintarBoton(hablando) {
    if (!boton) return;
    boton.classList.toggle('hablando', hablando);
    boton.setAttribute('aria-label', hablando ? 'Detener la lectura en voz alta' : 'Escuchar esta pantalla en voz alta');
    boton.querySelector('.btn-voz-texto').textContent = hablando ? 'Detener' : 'Escuchar';
  }
  window.addEventListener('sacks:voz', function (e) { pintarBoton(e.detail.hablando); });

  document.addEventListener('DOMContentLoaded', function () {
    boton = document.getElementById('btn-escuchar-pagina');
    if (boton) boton.addEventListener('click', alternar);
    observar();
    // Cada pantalla se lee al abrirse (después de que pantalla.js arma pestañas y páginas).
    setTimeout(function () { if (activa()) hablar(textoPagina()); }, 250);
  });
})();
