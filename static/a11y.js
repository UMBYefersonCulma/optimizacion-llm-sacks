/* Panel de accesibilidad · Frases de Sacks
   Preferencias persistentes (localStorage «sacks_a11y») aplicadas como clases/atributos en <html>.
   Pensado para baja visión, daltonismo, dislexia, motricidad reducida y uso con teclado o lector de pantalla.
   Voz: motor neuronal local Piper vía /api/voz (calidad natural) con respaldo en speechSynthesis del sistema. */
(function () {
  var CLAVE = 'sacks_a11y';
  var raiz = document.documentElement;
  var prefs = {};
  try { prefs = JSON.parse(localStorage.getItem(CLAVE) || '{}') || {}; } catch (e) { prefs = {}; }
  if (prefs.calma === undefined && window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) prefs.calma = true;

  var ESCALAS = [1, 1.25, 1.5, 2];          // WCAG 1.4.4: hasta 200 %
  var COLORES = [
    { id: 'normal',    nombre: 'Normal' },
    { id: 'contraste', nombre: 'Alto contraste', clase: 'a11y-contraste' },
    { id: 'oscuro',    nombre: 'Oscuro', clase: 'a11y-oscuro' },
    { id: 'invertido', nombre: 'Invertido', clase: 'a11y-invertido' },
    { id: 'gris',      nombre: 'Escala de grises', clase: 'a11y-gris' }
  ];
  var FUENTES = [
    { id: 'normal',   nombre: 'Normal (Poppins)' },
    { id: 'atkinson', nombre: 'Atkinson Hyperlegible · baja visión', clase: 'a11y-fuente-atkinson' },
    { id: 'lexend',   nombre: 'Lexend · lectura fluida', clase: 'a11y-fuente-lexend' },
    { id: 'dislexia', nombre: 'OpenDyslexic · dislexia', clase: 'a11y-fuente-dislexia' }
  ];
  var TOGGLES = [
    { id: 'espaciado', clase: 'a11y-espaciado', nombre: 'Espaciado de texto',  ayuda: 'Más separación entre letras, palabras y líneas.' },
    { id: 'guia',      clase: 'a11y-guia',      nombre: 'Guía de lectura',     ayuda: 'Una franja resaltada sigue al puntero para no perder la línea.' },
    { id: 'enlaces',   clase: 'a11y-enlaces',   nombre: 'Resaltar botones y enlaces', ayuda: 'Subraya y enmarca todo lo que se puede pulsar.' },
    { id: 'cursor',    clase: 'a11y-cursor',    nombre: 'Cursor grande',       ayuda: 'Puntero del mouse más grande y visible.' },
    { id: 'calma',     clase: 'a11y-calma',     nombre: 'Menos animaciones',   ayuda: 'Quita transiciones y movimientos.' },
    { id: 'voz',       clase: 'a11y-voz',       nombre: 'Leer en voz alta',    ayuda: 'Lee cada frase del test cuando aparece, con voz natural.' }
  ];

  function aplicar() {
    var escala = ESCALAS.indexOf(prefs.escala) >= 0 ? prefs.escala : 1;
    raiz.style.setProperty('--a11y-escala', escala);
    raiz.classList.toggle('a11y-grande', escala > 1);
    COLORES.forEach(function (c) { if (c.clase) raiz.classList.toggle(c.clase, prefs.color === c.id); });
    FUENTES.forEach(function (f) { if (f.clase) raiz.classList.toggle(f.clase, prefs.fuente === f.id); });
    TOGGLES.forEach(function (t) { raiz.classList.toggle(t.clase, !!prefs[t.id]); });
    try { localStorage.setItem(CLAVE, JSON.stringify(prefs)); } catch (e) {}
    guiaLectura(!!prefs.guia);
    try { window.dispatchEvent(new Event('sacks:diseno')); } catch (e) {}  // re-ajusta la paginación
  }

  // ── guía de lectura ──
  var guia = null;
  function guiaLectura(activa) {
    if (activa && !guia) {
      guia = document.createElement('div'); guia.className = 'a11y-guia-barra'; guia.setAttribute('aria-hidden', 'true');
      document.body.appendChild(guia);
      document.addEventListener('mousemove', moverGuia);
    } else if (!activa && guia) {
      document.removeEventListener('mousemove', moverGuia); guia.remove(); guia = null;
    }
  }
  function moverGuia(e) { if (guia) guia.style.top = (e.clientY - 22) + 'px'; }

  // ── voz ──
  var VOZ_SERVIDOR = null;   // {disponible, voces:[{id,nombre}], por_defecto}
  var audio = null, pendiente = null, vozSistema = null;
  var NOVEDAD = /^(eddy|flo|grandma|grandpa|reed|rocko|sandy|shelley|bells|bubbles|cellos|jester|organ|trinoids|whisper|wobble|zarvox|bad news|good news|junior|ralph|kathy|fred|albert)/i;
  var BUENAS = /^(paulina|m[oó]nica|jorge|diego|marisol|ang[eé]lica|carlos|francisca|soledad|helena|elvira|pablo|alvaro|laura|dalia|jimena|lorenzo|renata|isabela|mia|sofia|ximena)/i;
  function puntuar(v) {
    var lang = (v.lang || '').replace('_', '-').toLowerCase();
    var orden = ['es-co', 'es-mx', 'es-us', 'es-419', 'es-es', 'es'];
    var p = -1; for (var i = 0; i < orden.length; i++) if (lang.indexOf(orden[i]) === 0) { p = i; break; }
    if (p < 0) return -1;
    var nombre = v.name || '';
    var calidad = NOVEDAD.test(nombre) ? -60 : (BUENAS.test(nombre) ? 30 : 0);
    if (/enhanced|premium|mejorad|neural|natural/i.test(nombre)) calidad += 20;
    return (v.localService ? 100 : 0) + calidad + (10 - p) + (v.default ? 1 : 0);
  }
  function elegirVozSistema() {
    if (!('speechSynthesis' in window)) return;
    var mejor = null, mejorP = -1;
    speechSynthesis.getVoices().forEach(function (v) { var s = puntuar(v); if (s > mejorP) { mejorP = s; mejor = v; } });
    vozSistema = mejor;
  }
  if ('speechSynthesis' in window) {
    elegirVozSistema();
    speechSynthesis.addEventListener('voiceschanged', elegirVozSistema);
  }
  window.addEventListener('pagehide', function () { window.sacksCallar(); });

  function velocidad() { var v = parseFloat(prefs.velocidad); return isNaN(v) ? 1 : Math.min(1.4, Math.max(0.6, v)); }
  function motor() {
    if (prefs.motor === 'sistema') return 'sistema';
    return (VOZ_SERVIDOR && VOZ_SERVIDOR.disponible) ? 'servidor' : 'sistema';
  }
  function hablarSistema(texto) {
    if (!('speechSynthesis' in window)) return false;
    speechSynthesis.cancel();
    var u = new SpeechSynthesisUtterance(texto);
    if (vozSistema) { u.voice = vozSistema; u.lang = vozSistema.lang; } else { u.lang = 'es-CO'; }
    u.rate = velocidad() * 0.95;
    u.onerror = function (ev) { if (ev.error === 'not-allowed') pendiente = texto; };
    speechSynthesis.speak(u);
    return true;
  }
  function hablarServidor(texto) {
    if (!audio) { audio = new Audio(); audio.preload = 'auto'; }
    try { audio.pause(); } catch (e) {}
    var voz = prefs.vozId || (VOZ_SERVIDOR && VOZ_SERVIDOR.por_defecto) || 'mx';
    audio.src = '/api/voz?voz=' + encodeURIComponent(voz) + '&velocidad=' + velocidad().toFixed(2) + '&texto=' + encodeURIComponent(texto);
    var p = audio.play();
    if (p && p.catch) p.catch(function (err) {
      if (err && err.name === 'NotAllowedError') pendiente = texto;   // autoplay bloqueado: se reintenta con el próximo gesto
      else hablarSistema(texto);                                        // servidor caído: respaldo del sistema
    });
    return true;
  }
  window.sacksHablar = function (texto, forzar) {
    if (!texto) return false;
    if (!forzar && !prefs.voz) return false;
    window.sacksCallar();
    return motor() === 'servidor' ? hablarServidor(texto) : hablarSistema(texto);
  };
  window.sacksCallar = function () {
    if ('speechSynthesis' in window) speechSynthesis.cancel();
    if (audio) { try { audio.pause(); audio.currentTime = 0; } catch (e) {} }
  };
  window.sacksVozActiva = function () { return !!prefs.voz; };
  ['pointerdown', 'keydown'].forEach(function (t) {
    document.addEventListener(t, function () { if (pendiente) { var s = pendiente; pendiente = null; window.sacksHablar(s, true); } }, true);
  });
  fetch('/api/estado').then(function (r) { return r.json(); }).then(function (s) { VOZ_SERVIDOR = s.voz || null; pintarVoces(); }).catch(function () {});

  // ── panel ──
  var panel, boton, selectVoz, selectMotor;
  function el(tag, attrs, hijos) {
    var e = document.createElement(tag);
    for (var k in (attrs || {})) { if (k === 'text') e.textContent = attrs[k]; else if (k === 'html') e.innerHTML = attrs[k]; else e.setAttribute(k, attrs[k]); }
    (hijos || []).forEach(function (h) { if (h) e.appendChild(h); });
    return e;
  }
  function seccion(titulo, hijos) { return el('div', { class: 'a11y-seccion' }, [el('h3', { text: titulo })].concat(hijos)); }
  function grupoRadios(nombre, opciones, valor, onchange) {
    var wrap = el('div', { class: 'a11y-radios', role: 'radiogroup', 'aria-label': nombre });
    opciones.forEach(function (o) {
      var input = el('input', { type: 'radio', name: 'a11y-' + nombre, value: o.id, id: 'a11y-' + nombre + '-' + o.id });
      input.checked = (valor || 'normal') === o.id;
      input.addEventListener('change', function () { onchange(o.id); });
      wrap.appendChild(el('label', { class: 'a11y-radio', for: input.id }, [input, el('span', { text: o.nombre })]));
    });
    return wrap;
  }
  function pintarVoces() {
    if (!selectMotor) return;
    var tieneServidor = VOZ_SERVIDOR && VOZ_SERVIDOR.disponible;
    selectMotor.innerHTML = '';
    if (tieneServidor) selectMotor.appendChild(el('option', { value: 'servidor', text: 'Voz natural (en este equipo)' }));
    selectMotor.appendChild(el('option', { value: 'sistema', text: 'Voz del sistema' }));
    selectMotor.value = (prefs.motor === 'sistema' || !tieneServidor) ? 'sistema' : 'servidor';
    selectVoz.innerHTML = '';
    if (tieneServidor) {
      VOZ_SERVIDOR.voces.forEach(function (v) { selectVoz.appendChild(el('option', { value: v.id, text: v.nombre })); });
      selectVoz.value = prefs.vozId || VOZ_SERVIDOR.por_defecto;
    }
    selectVoz.parentNode.hidden = !tieneServidor || selectMotor.value === 'sistema';
  }
  function construir() {
    boton = document.getElementById('btn-a11y'); panel = document.getElementById('panel-a11y');
    if (!boton || !panel) return;
    panel.innerHTML = '';
    var cabecera = el('div', { class: 'a11y-cabecera' }, [el('strong', { text: 'Accesibilidad' }), el('button', { type: 'button', class: 'a11y-cerrar', 'aria-label': 'Cerrar panel', text: '✕' })]);
    panel.appendChild(cabecera);
    var col1 = el('div', { class: 'a11y-col' }), col2 = el('div', { class: 'a11y-col' });
    panel.appendChild(el('div', { class: 'a11y-columnas' }, [col1, col2]));

    var etiquetaEscala = el('span', { class: 'a11y-valor', 'aria-live': 'polite' });
    function pintarEscala() { etiquetaEscala.textContent = Math.round((ESCALAS.indexOf(prefs.escala) >= 0 ? prefs.escala : 1) * 100) + ' %'; }
    var menos = el('button', { type: 'button', class: 'a11y-paso', 'aria-label': 'Texto más pequeño', text: 'A−' });
    var mas = el('button', { type: 'button', class: 'a11y-paso', 'aria-label': 'Texto más grande', text: 'A+' });
    function cambiarEscala(d) { var i = Math.max(0, ESCALAS.indexOf(prefs.escala)); i = Math.min(ESCALAS.length - 1, Math.max(0, i + d)); prefs.escala = ESCALAS[i]; aplicar(); pintarEscala(); }
    menos.addEventListener('click', function () { cambiarEscala(-1); });
    mas.addEventListener('click', function () { cambiarEscala(1); });
    pintarEscala();
    col1.appendChild(seccion('Tamaño del texto', [el('div', { class: 'a11y-fila' }, [menos, etiquetaEscala, mas])]));
    col1.appendChild(seccion('Colores', [grupoRadios('color', COLORES, prefs.color, function (v) { prefs.color = v; aplicar(); })]));
    col1.appendChild(seccion('Tipo de letra', [grupoRadios('fuente', FUENTES, prefs.fuente, function (v) { prefs.fuente = v; aplicar(); })]));

    var lista = el('div', { class: 'a11y-lista' });
    TOGGLES.forEach(function (t) {
      var chk = el('input', { type: 'checkbox', id: 'a11y-' + t.id, role: 'switch' }); chk.checked = !!prefs[t.id]; chk.setAttribute('aria-checked', chk.checked);
      chk.addEventListener('change', function () {
        prefs[t.id] = chk.checked; chk.setAttribute('aria-checked', chk.checked); aplicar();
        if (t.id === 'voz') { if (chk.checked) window.sacksHablar('Lectura en voz alta activada.', true); else window.sacksCallar(); }
      });
      lista.appendChild(el('label', { class: 'a11y-opcion', for: chk.id }, [chk, el('span', { html: '<strong>' + t.nombre + '</strong><small>' + t.ayuda + '</small>' })]));
    });
    col2.appendChild(seccion('Lectura y navegación', [lista]));

    selectMotor = el('select', { id: 'a11y-motor', 'aria-label': 'Motor de voz' });
    selectVoz = el('select', { id: 'a11y-vozid', 'aria-label': 'Voz' });
    selectMotor.addEventListener('change', function () { prefs.motor = selectMotor.value; aplicar(); pintarVoces(); });
    selectVoz.addEventListener('change', function () { prefs.vozId = selectVoz.value; aplicar(); });
    var rango = el('input', { type: 'range', min: '0.6', max: '1.4', step: '0.1', id: 'a11y-vel', 'aria-label': 'Velocidad de la voz' }); rango.value = velocidad();
    var valVel = el('span', { class: 'a11y-valor', text: '×' + velocidad().toFixed(1) });
    rango.addEventListener('input', function () { prefs.velocidad = parseFloat(rango.value); valVel.textContent = '×' + velocidad().toFixed(1); aplicar(); });
    var probar = el('button', { type: 'button', class: 'chip', text: '▶ Probar voz' });
    probar.addEventListener('click', function () { window.sacksHablar('Hola. Así se escucha la lectura en voz alta.', true); });
    var detener = el('button', { type: 'button', class: 'chip', text: '■ Detener' });
    detener.addEventListener('click', function () { window.sacksCallar(); });
    col2.appendChild(seccion('Voz', [
      el('div', { class: 'a11y-campo' }, [el('label', { for: 'a11y-motor', text: 'Motor' }), selectMotor]),
      el('div', { class: 'a11y-campo' }, [el('label', { for: 'a11y-vozid', text: 'Voz' }), selectVoz]),
      el('div', { class: 'a11y-campo' }, [el('label', { for: 'a11y-vel', text: 'Velocidad' }), el('div', { class: 'a11y-fila' }, [rango, valVel])]),
      el('div', { class: 'a11y-fila' }, [probar, detener])
    ]));
    pintarVoces();

    var reset = el('button', { type: 'button', class: 'chip a11y-reset', text: 'Restablecer todo' });
    reset.addEventListener('click', function () { prefs = {}; aplicar(); window.sacksCallar(); construir(); abrir(true); });
    panel.appendChild(el('div', { class: 'a11y-pie' }, [reset, el('small', { text: 'Atajo: Alt + A' })]));
    cabecera.querySelector('.a11y-cerrar').addEventListener('click', function () { abrir(false); boton.focus(); });
  }
  function abrir(v) {
    if (!panel) return;
    panel.hidden = !v; boton.setAttribute('aria-expanded', v ? 'true' : 'false');
    if (v) { var f = panel.querySelector('button.a11y-paso, input, select'); if (f) f.focus(); }
  }
  function iniciar() {
    construir();
    if (!boton) return;
    boton.addEventListener('click', function () { abrir(panel.hidden); });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !panel.hidden) { abrir(false); boton.focus(); }
      if (e.altKey && e.code === 'KeyA' && !e.ctrlKey && !e.metaKey) { e.preventDefault(); abrir(panel.hidden); }
    });
    document.addEventListener('click', function (e) { if (!panel.hidden && !e.target.closest('#panel-a11y') && !e.target.closest('#btn-a11y')) abrir(false); });
  }
  aplicar();
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', iniciar); else iniciar();
})();
