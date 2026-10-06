"""
Cliente del modelo local para el proyecto "Frases de Sacks".

Habla con Ollama por HTTP (http://localhost:11434) en lugar de invocar el CLI
`ollama run`, porque el CLI mezcla en stdout el bloque de razonamiento
("Thinking... / ...done thinking.") y códigos de escape ANSI. La API devuelve
la respuesta final limpia en `message.content` y el razonamiento aparte en
`message.thinking`, lo que hace el parseo determinista.

El modelo custom `deepseek-r1-sacks` (DeepSeek-R1 7B + system prompt en
español, temperatura 0) responde únicamente en este formato:

    Frase: <FRASE>
    Clasificación emocional: <POSITIVA / NEGATIVA / AMBIGUA>
    Razón: <1 o 2 frases>
"""

from __future__ import annotations

import csv
import os
import re
import threading
import time
import unicodedata
from dataclasses import dataclass, asdict
from datetime import datetime

import requests

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
MODELO = os.environ.get("SACKS_MODELO", "deepseek-r1-sacks")
TIMEOUT_SEGUNDOS = float(os.environ.get("SACKS_TIMEOUT", "180"))
KEEP_ALIVE = os.environ.get("SACKS_KEEP_ALIVE", "2h")  # mantener el modelo cargado durante la sustentación

# MODO de inferencia:
#   "rapido": se omite la cadena de razonamiento larga de DeepSeek-R1 rellenando un bloque <think> vacío
#             (≈3 s por frase). Requiere enviar el prompt "crudo" con la plantilla del modelo.
#   "think":  razonamiento completo vía /api/chat (≈15 s por frase).
MODO = os.environ.get("SACKS_MODO", "rapido")
# Ejemplos etiquetados por psicólogos del mismo enunciado que se agregan al mensaje (0 = desactivado).
FEWSHOT = int(os.environ.get("SACKS_FEWSHOT", "8"))
# «Memoria de casos»: si la respuesta es casi idéntica (similitud ≥ umbral) a una ya clasificada por los
# psicólogos para el mismo enunciado, se usa esa clasificación sin consultar al modelo (0 = desactivado).
UMBRAL_CASOS = float(os.environ.get("SACKS_CASOS_UMBRAL", "0.85"))

CATEGORIAS = ("POSITIVA", "NEGATIVA", "AMBIGUA")

# Mismas opciones en el precalentado y en cada clasificación: si cambian (p. ej. num_ctx),
# Ollama recarga el modelo y la primera frase de la demo paga otra vez el arranque en frío.
OPCIONES_MODELO = {
    "temperature": 0,     # determinista: mismo resultado que en las evaluaciones
    "num_ctx": 4096,      # el prompt es corto; menos memoria y carga más rápida
    "num_predict": 1200,  # techo de seguridad para razonamientos que se alargan
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOGS_DIR = os.path.join(BASE_DIR, "logs")
LOG_CSV = os.path.join(LOGS_DIR, "log.csv")

# Ollama atiende una petición a la vez por defecto; serializamos para que dos
# flujos simultáneos (p. ej. CSV en curso + clasificación individual) no se pisen.
_lock_modelo = threading.Lock()
_lock_log = threading.Lock()

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINKING_CLI_RE = re.compile(r"^\s*Thinking\.\.\..*?\.\.\.done thinking\.\s*", re.DOTALL | re.IGNORECASE)


class LLMError(RuntimeError):
    """Error al consultar el modelo (Ollama caído, modelo ausente, timeout, respuesta inválida)."""


@dataclass
class Clasificacion:
    frase: str
    edad: str
    genero: str
    categoria: str
    razon: str
    frase_modelo: str
    duracion_s: float
    raw: str
    thinking: str
    fuente: str = "modelo"  # "modelo" (DeepSeek-R1) o "casos" (respuesta ya clasificada por psicólogos)

    def fila(self) -> dict:
        return {
            "Edad": self.edad,
            "Genero": self.genero,
            "Frase": self.frase,
            "Categoria": self.categoria,
            "Razon": self.razon,
            "Fuente": self.fuente,
        }


# ───────────────────────── utilidades de texto ───────────────────────── #

def _sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def normalizar_categoria(valor) -> str:
    """
    Lleva cualquier variante a POSITIVA / NEGATIVA / AMBIGUA o "" si no se reconoce.
    Acepta masculino/femenino, mayúsculas/minúsculas, acentos, puntuación, markdown, inglés.
    «Neutra/neutro» (categoría antigua del proyecto y del dataset) se asimila a AMBIGUA: sin evidencia emocional.
    """
    if valor is None:
        return ""
    texto = _sin_acentos(str(valor)).lower()
    texto = re.sub(r"[*_`\"'.,;:!¡?¿()\[\]]", " ", texto).strip()
    if not texto or texto in ("nan", "none"):
        return ""
    if re.search(r"\bposit", texto):
        return "POSITIVA"
    if re.search(r"\bnegat", texto):
        return "NEGATIVA"
    if re.search(r"\bambig", texto):
        return "AMBIGUA"
    if re.search(r"\bneutr", texto):
        return "AMBIGUA"
    return ""


def limpiar_salida(texto: str) -> str:
    """Quita ANSI, bloques <think> y el bloque 'Thinking...' del CLI, por si acaso."""
    texto = _ANSI_RE.sub("", texto or "")
    texto = _THINK_RE.sub("", texto)
    texto = _THINKING_CLI_RE.sub("", texto)
    return texto.strip()


def extraer_respuesta(salida: str) -> dict:
    """
    Parsea el bloque Frase / Clasificación emocional / Razón de forma tolerante:
    mayúsculas, acentos, negrita markdown, puntuación final y razón multilínea.
    """
    limpio = limpiar_salida(salida)
    res = {"frase": "", "categoria": "", "razon": ""}

    m = re.search(r"frase\s*:\s*\**\s*(.+)", limpio, re.IGNORECASE)
    if m:
        res["frase"] = m.group(1).strip().strip("*").strip().strip('"').strip()

    m = re.search(r"clasificaci[oó]n\s+emocional\s*:\s*\**\s*([A-Za-zÁÉÍÓÚáéíóú]+)", limpio, re.IGNORECASE)
    if m:
        res["categoria"] = normalizar_categoria(m.group(1))

    m = re.search(r"raz[oó]n\s*:\s*\**\s*(.+?)(?:\n\s*\n|\Z)", limpio, re.IGNORECASE | re.DOTALL)
    if m:
        razon = " ".join(line.strip() for line in m.group(1).strip().splitlines() if line.strip())
        res["razon"] = razon.strip("*").strip()

    if not res["categoria"]:
        # Último recurso: la primera categoría que aparezca en el texto limpio.
        for cat in CATEGORIAS:
            if re.search(rf"\b{cat}\b", limpio, re.IGNORECASE):
                res["categoria"] = cat
                break
    res["razon"] = pulir_razon(res["razon"], res["categoria"])
    return res


# El destilado de 7B a veces mezcla palabras en inglés en la razón («es always NEGATIVA»).
_INGLES_SUELTO = {"always": "siempre", "never": "nunca", "however": "sin embargo", "although": "aunque",
                  "because": "porque", "but": "pero", "also": "también", "very": "muy"}
_INGLES_FUNCION = re.compile(r"\b(the|and|it|to|of|is|as|with|which|this|that|leading|uses|an)\b", re.IGNORECASE)


# El modelo a veces justifica con «la polaridad se invierte por el marco negativo» en enunciados que no lo tienen
# («Si yo estuviera a cargo…»). Solo afecta la explicación; la categoría no cambia.
_MENCION_MARCO = re.compile(r"marco negativo|enunciado negativo|polaridad se invierte|invierte la polaridad|polaridad invertida", re.I)
_ENUNCIADO_NEGATIVO = re.compile(r"raras veces|no me gusta|menos me gusta|olvidar|miedo|peor|error|mala suerte|en contra|culpa", re.I)


def limpiar_marco(razon: str, enunciado: str, categoria: str = "") -> str:
    if not razon or not _MENCION_MARCO.search(razon) or _ENUNCIADO_NEGATIVO.search(enunciado or ""):
        return razon
    partes = re.split(r",\s*pero\s+", razon, maxsplit=1)
    if len(partes) == 2 and _MENCION_MARCO.search(partes[0]):
        resto = partes[1].strip()
    else:
        resto = " ".join(x for x in re.split(r"(?<=[.;])\s+", razon) if not _MENCION_MARCO.search(x)).strip()
    if len(resto) < 12:
        return f"La respuesta expresa una carga emocional {categoria.lower()} frente al enunciado." if categoria else razon
    return resto[0].upper() + resto[1:]


def pulir_razon(razon: str, categoria: str = "") -> str:
    """Traduce palabras sueltas en inglés y, si la razón quedó mayormente en inglés, usa una explicación neutra."""
    if not razon:
        return razon
    for en, es in _INGLES_SUELTO.items():
        razon = re.sub(rf"\b{en}\b", es, razon, flags=re.IGNORECASE)
    if len(_INGLES_FUNCION.findall(razon)) >= 3 and categoria:
        return f"La respuesta expresa una carga emocional {categoria.lower()} frente al enunciado."
    return razon


# ───────────────────────── acceso a Ollama ───────────────────────── #

def estado_ollama() -> dict:
    """Devuelve {'ok': bool, 'modelo_presente': bool, 'modelos': [...], 'error': str}."""
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        r.raise_for_status()
        nombres = [m.get("name", "") for m in r.json().get("models", [])]
        presente = any(n == MODELO or n.split(":")[0] == MODELO for n in nombres)
        return {"ok": True, "modelo_presente": presente, "modelos": nombres, "error": ""}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "modelo_presente": False, "modelos": [], "error": str(e)}


def _construir_prompt(frase: str, edad, genero, numero=None, respuesta: str = "") -> str:
    edad_txt = str(edad).strip() if edad not in (None, "") else "No especificada"
    genero_txt = str(genero).strip() if genero not in (None, "") else "No especificado"
    fewshot = ""
    if FEWSHOT and numero not in (None, ""):
        import sacks_ejemplos  # import tardío: el dataset solo se carga si se usa
        fewshot = sacks_ejemplos.bloque_fewshot(numero, FEWSHOT, genero_txt, respuesta)
        if fewshot:
            fewshot += "\n"
    return f"{fewshot}Edad: {edad_txt}\nGénero: {genero_txt}\nFrase: {frase.strip()}"


_system_cache: dict[str, str] = {}


def system_prompt() -> str:
    """Prompt de sistema del modelo (desde Ollama), necesario para el modo rápido con prompt crudo."""
    if MODELO not in _system_cache:
        r = requests.post(f"{OLLAMA_BASE_URL}/api/show", json={"model": MODELO}, timeout=15)
        r.raise_for_status()
        _system_cache[MODELO] = (r.json().get("system") or "").strip()
    return _system_cache[MODELO]


def _peticion_modelo(mensaje: str, timeout: float) -> tuple[str, str]:
    """Llama al modelo según MODO y devuelve (contenido, razonamiento)."""
    if MODO == "rapido":
        crudo = f"{system_prompt()}<｜User｜>{mensaje}<｜Assistant｜><think>\n\n</think>\n\n"
        payload = {"model": MODELO, "stream": False, "raw": True, "prompt": crudo, "keep_alive": KEEP_ALIVE,
                   "options": dict(OPCIONES_MODELO, num_predict=220)}
        r = requests.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=timeout)
        _verificar_respuesta(r)
        return (r.json().get("response") or "").strip(), ""
    payload = {"model": MODELO, "stream": False, "keep_alive": KEEP_ALIVE, "options": OPCIONES_MODELO,
               "messages": [{"role": "user", "content": mensaje}]}
    r = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=timeout)
    _verificar_respuesta(r)
    mensaje_r = r.json().get("message", {}) or {}
    return (mensaje_r.get("content") or "").strip(), (mensaje_r.get("thinking") or "").strip()


def _verificar_respuesta(r) -> None:
    if r.status_code == 404:
        raise LLMError(f"El modelo '{MODELO}' no está instalado en Ollama. "
                       f"Ejecuta: ollama create {MODELO} -f Modelfile")
    if r.status_code != 200:
        raise LLMError(f"Ollama respondió {r.status_code}: {r.text[:300]}")


def _registrar_log(registro: dict) -> None:
    try:
        os.makedirs(LOGS_DIR, exist_ok=True)
        campos = ["timestamp", "modelo", "edad", "genero", "frase", "categoria", "razon",
                  "duracion_s", "frase_modelo", "raw", "fuente"]
        with _lock_log:
            nuevo = not os.path.exists(LOG_CSV)
            with open(LOG_CSV, "a", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
                if nuevo:
                    w.writeheader()
                w.writerow(registro)
    except OSError:
        pass  # el log nunca debe tumbar una clasificación


def clasificar(frase: str, edad="", genero="", timeout: float | None = None,
               numero=None, respuesta: str = "") -> Clasificacion:
    """
    Clasifica UNA frase con el modelo local. Lanza LLMError si algo sale mal.
    `numero` (enunciado de Sacks) activa los ejemplos few-shot de ese enunciado; `respuesta` es
    la parte escrita por la persona (para no incluirla como ejemplo).
    """
    frase = (frase or "").strip()
    if not frase:
        raise LLMError("La frase está vacía.")

    # «Memoria de casos»: respuesta casi idéntica a una ya clasificada por los psicólogos del proyecto.
    if UMBRAL_CASOS > 0 and numero not in (None, "") and (respuesta or "").strip():
        import sacks_ejemplos
        similitud, caso = sacks_ejemplos.vecino_mas_cercano(numero, respuesta, UMBRAL_CASOS)
        if caso:
            resultado = Clasificacion(
                frase=frase, edad="" if edad in (None, "") else str(edad),
                genero="" if genero in (None, "") else str(genero),
                categoria=caso["Categoria"],
                razon=(f"Coincide con la respuesta «{caso['Respuesta']}», ya clasificada por los psicólogos "
                       f"del proyecto como {caso['Categoria']} (similitud {similitud:.0%})."),
                frase_modelo=frase, duracion_s=0.0, raw="", thinking="", fuente="casos",
            )
            _registrar_log({"timestamp": datetime.now().isoformat(timespec="seconds"), "modelo": "casos-psicologos",
                            **{k: v for k, v in asdict(resultado).items() if k != "thinking"}})
            return resultado

    mensaje = _construir_prompt(frase, edad, genero, numero, respuesta)
    inicio = time.time()
    with _lock_modelo:
        try:
            contenido, thinking = _peticion_modelo(mensaje, timeout or TIMEOUT_SEGUNDOS)
        except requests.exceptions.ConnectionError as e:
            raise LLMError("No se pudo conectar con Ollama en "
                           f"{OLLAMA_BASE_URL}. ¿Está abierta la aplicación Ollama? ({e.__class__.__name__})") from e
        except requests.exceptions.Timeout as e:
            raise LLMError(f"El modelo tardó más de {timeout or TIMEOUT_SEGUNDOS:.0f} s en responder.") from e
    duracion = time.time() - inicio

    parsed = extraer_respuesta(contenido)
    if numero not in (None, ""):
        try:
            import sacks_items
            enunciado = sacks_items.enunciado(int(numero), genero)
        except (TypeError, ValueError, KeyError, IndexError):
            enunciado = frase
    elif respuesta and frase.endswith(respuesta.strip()):
        enunciado = frase[: len(frase) - len(respuesta.strip())]
    else:
        enunciado = frase
    parsed["razon"] = limpiar_marco(parsed["razon"], enunciado, parsed["categoria"])
    if not parsed["categoria"]:
        raise LLMError("El modelo respondió en un formato inesperado: " + (limpiar_salida(contenido)[:200] or "(vacío)"))

    resultado = Clasificacion(
        frase=frase,
        edad="" if edad in (None, "") else str(edad),
        genero="" if genero in (None, "") else str(genero),
        categoria=parsed["categoria"],
        razon=parsed["razon"] or "(sin razón)",
        frase_modelo=parsed["frase"],
        duracion_s=round(duracion, 1),
        raw=contenido,
        thinking=thinking,
    )
    _registrar_log({"timestamp": datetime.now().isoformat(timespec="seconds"), "modelo": MODELO,
                    **{k: v for k, v in asdict(resultado).items() if k != "thinking"}})
    return resultado


def precalentar(en_segundo_plano: bool = True) -> None:
    """Carga el modelo en memoria para que la primera clasificación de la demo no tarde 20 s."""
    def _run():
        try:
            requests.post(f"{OLLAMA_BASE_URL}/api/generate",
                          json={"model": MODELO, "prompt": "", "keep_alive": KEEP_ALIVE,
                                "options": OPCIONES_MODELO},
                          timeout=120)
        except Exception:  # noqa: BLE001
            pass
    if en_segundo_plano:
        threading.Thread(target=_run, daemon=True, name="precalentar-modelo").start()
    else:
        _run()
