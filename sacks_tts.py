"""
Voz en español 100 % local con Piper (motor neuronal open source, licencia MIT).

Las voces (.onnx + .onnx.json) viven en data/voces/. Se descargaron de
https://huggingface.co/rhasspy/piper-voices (licencias de cada voz en su .json).
La app expone GET /api/voz?texto=…&voz=… que devuelve un WAV; el navegador lo reproduce.
Si Piper o las voces no están disponibles, el panel de accesibilidad recurre a la voz
del sistema (speechSynthesis) automáticamente.
"""

from __future__ import annotations

import hashlib
import io
import os
import threading
import wave
from collections import OrderedDict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VOCES_DIR = os.path.join(BASE_DIR, "data", "voces")

# id -> (archivo, nombre visible, descripción)
VOCES = OrderedDict([
    ("mx", ("es_MX-claude-high.onnx", "Claudia · México", "Voz femenina, acento mexicano (alta calidad)")),
    ("es", ("es_ES-sharvard-medium.onnx", "Sara · España", "Voz femenina, acento de España")),
])
VOZ_POR_DEFECTO = "mx"

_voces_cargadas: dict[str, object] = {}
_lock = threading.Lock()
_cache: OrderedDict[str, bytes] = OrderedDict()
_CACHE_MAX = 400


def disponible() -> bool:
    try:
        import piper  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return any(os.path.isfile(os.path.join(VOCES_DIR, v[0])) and os.path.isfile(os.path.join(VOCES_DIR, v[0] + ".json"))
               for v in VOCES.values())


def voces_disponibles() -> list[dict]:
    salida = []
    for vid, (archivo, nombre, desc) in VOCES.items():
        ruta = os.path.join(VOCES_DIR, archivo)
        if os.path.isfile(ruta) and os.path.isfile(ruta + ".json"):
            salida.append({"id": vid, "nombre": nombre, "descripcion": desc})
    return salida


def _cargar(vid: str):
    from piper import PiperVoice
    if vid not in VOCES:
        vid = VOZ_POR_DEFECTO
    with _lock:
        if vid not in _voces_cargadas:
            ruta = os.path.join(VOCES_DIR, VOCES[vid][0])
            _voces_cargadas[vid] = PiperVoice.load(ruta)
    return _voces_cargadas[vid]


def sintetizar(texto: str, vid: str = VOZ_POR_DEFECTO, velocidad: float = 1.0) -> bytes:
    """Devuelve un WAV (bytes). velocidad 1.0 = normal; 0.8 más lenta; 1.2 más rápida."""
    texto = " ".join((texto or "").split())[:600]
    if not texto:
        raise ValueError("Texto vacío")
    velocidad = min(1.6, max(0.6, float(velocidad or 1.0)))
    clave = hashlib.sha1(f"{vid}|{velocidad:.2f}|{texto}".encode("utf-8")).hexdigest()
    with _lock:
        if clave in _cache:
            _cache.move_to_end(clave)
            return _cache[clave]
    voz = _cargar(vid)
    buf = io.BytesIO()
    try:
        from piper import SynthesisConfig
        cfg = SynthesisConfig(length_scale=1.0 / velocidad)
    except Exception:  # noqa: BLE001 — versiones antiguas de piper
        cfg = None
    with _lock:
        with wave.open(buf, "wb") as w:
            if cfg is not None:
                voz.synthesize_wav(texto, w, syn_config=cfg)
            else:
                voz.synthesize_wav(texto, w)
    datos = buf.getvalue()
    with _lock:
        _cache[clave] = datos
        if len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)
    return datos


def precalentar(en_segundo_plano: bool = True) -> None:
    def _run():
        try:
            if disponible():
                sintetizar("Bienvenido al test de frases incompletas.", VOZ_POR_DEFECTO)
        except Exception:  # noqa: BLE001
            pass
    if en_segundo_plano:
        threading.Thread(target=_run, daemon=True, name="precalentar-voz").start()
    else:
        _run()
