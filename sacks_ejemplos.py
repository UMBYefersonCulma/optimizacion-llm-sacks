"""
Ejemplos etiquetados por psicólogos (dataset del proyecto, 52 personas × 60 enunciados) para
guiar al modelo con few-shot del MISMO enunciado. Fuente: data/ejemplos_psicologos.csv
(extraído de «Cod. PROYECTO DE ENTRENAMIENTO DE UN MODELO DE LENGUAJE GRANDE (LLM) EN ESPAÑOL.xlsx»).
"""

from __future__ import annotations

import csv
import os
import random
import re
from collections import Counter, defaultdict
from functools import lru_cache

import sacks_items

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUTA = os.path.join(BASE_DIR, "data", "ejemplos_psicologos.csv")
ORDEN_CATEGORIAS = ("POSITIVA", "NEGATIVA", "AMBIGUA")
# El dataset original tiene también «NEUTRA»; el proyecto la eliminó y se asimila a AMBIGUA (sin evidencia).
_ASIMILAR = {"NEUTRA": "AMBIGUA"}


@lru_cache(maxsize=1)
def _por_enunciado() -> dict[int, list[dict]]:
    salida: dict[int, list[dict]] = defaultdict(list)
    if not os.path.isfile(RUTA):
        return salida
    with open(RUTA, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                n = int(r["Numero"]); persona = int(r.get("persona") or 0)
            except (TypeError, ValueError):
                continue
            resp = (r["Respuesta"] or "").strip()
            cat = _ASIMILAR.get(r["Categoria"], r["Categoria"])
            # Se descartan respuestas vacías, demasiado largas o sin letras (ruido de captura).
            if cat not in ORDEN_CATEGORIAS or not re.search(r"[a-zA-ZáéíóúñÁÉÍÓÚÑ]", resp) or len(resp) > 90:
                continue
            salida[n].append({"persona": persona, "Respuesta": resp, "Genero": r["Genero"], "Categoria": cat})
    return salida


def disponibles() -> int:
    return sum(len(v) for v in _por_enunciado().values())


def distribucion(numero) -> Counter:
    return Counter(e["Categoria"] for e in _por_enunciado().get(int(numero), []))


def ejemplos_para(numero, k: int = 8, genero: str = "", excluir_respuesta: str = "",
                  excluir_personas=(), modo: str = "proporcional") -> list[dict]:
    """
    Devuelve hasta k ejemplos del mismo enunciado.
      modo "proporcional": las categorías aparecen en la proporción en que los psicólogos las usaron
                           para ese enunciado (el modelo aprende el "prior" real del ítem).
      modo "balanceado":   alterna categorías por igual.
    Selección determinista por enunciado (misma lista en cada llamada).
    """
    try:
        n = int(numero)
    except (TypeError, ValueError):
        return []
    excluir = set(excluir_personas or ())
    candidatos = [e for e in _por_enunciado().get(n, [])
                  if e["persona"] not in excluir
                  and e["Respuesta"].lower() != (excluir_respuesta or "").strip().lower()]
    if not candidatos or k <= 0:
        return []
    rng = random.Random(1000 + n)
    rng.shuffle(candidatos)
    por_cat: dict[str, list[dict]] = defaultdict(list)
    for e in candidatos:
        por_cat[e["Categoria"]].append(e)

    seleccion: list[dict] = []
    if modo == "proporcional":
        total = len(candidatos)
        cupos = {c: (len(por_cat[c]) * k) / total for c in ORDEN_CATEGORIAS}
        asignados = {c: int(cupos[c]) for c in ORDEN_CATEGORIAS}
        # una categoría con presencia real (≥ 10 %) merece al menos un ejemplo
        for c in ORDEN_CATEGORIAS:
            if asignados[c] == 0 and por_cat[c] and len(por_cat[c]) / total >= 0.10:
                asignados[c] = 1
        # repartir cupos restantes por mayor resto
        while sum(asignados.values()) < k and any(len(por_cat[c]) > asignados[c] for c in ORDEN_CATEGORIAS):
            c = max((c for c in ORDEN_CATEGORIAS if len(por_cat[c]) > asignados[c]), key=lambda c: cupos[c] - asignados[c])
            asignados[c] += 1
        while sum(asignados.values()) > k:
            c = max((c for c in ORDEN_CATEGORIAS if asignados[c] > 1), key=lambda c: asignados[c], default=None)
            if c is None:
                break
            asignados[c] -= 1
        # intercalar para que no queden bloques por categoría
        colas = {c: por_cat[c][:asignados[c]] for c in ORDEN_CATEGORIAS}
        while len(seleccion) < k and any(colas.values()):
            for c in ORDEN_CATEGORIAS:
                if colas[c] and len(seleccion) < k:
                    seleccion.append(colas[c].pop())
    else:
        while len(seleccion) < k and any(por_cat.values()):
            for c in ORDEN_CATEGORIAS:
                if por_cat[c] and len(seleccion) < k:
                    seleccion.append(por_cat[c].pop())
    return [dict(e, Frase=sacks_items.frase_completa(n, e["Respuesta"], genero or e["Genero"])) for e in seleccion]


def _normalizar(texto: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFD", (texto or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9ñ ]+", " ", t)).strip()


def vecino_mas_cercano(numero, respuesta: str, umbral: float = 0.85, excluir_personas=()) -> tuple[float, dict | None]:
    """
    «Memoria de casos»: busca, entre las respuestas ya clasificadas por psicólogos para el MISMO
    enunciado, la más parecida a la respuesta dada (similitud léxica difflib). Devuelve (similitud, ejemplo)
    solo si supera el umbral; medido sobre datos no vistos, con umbral 0.8-0.9 acierta 91-100 %.
    """
    import difflib
    try:
        n = int(numero)
    except (TypeError, ValueError):
        return 0.0, None
    objetivo = _normalizar(respuesta)
    if len(objetivo) < 3:
        return 0.0, None
    excluir = set(excluir_personas or ())
    mejor, ejemplo = 0.0, None
    for e in _por_enunciado().get(n, []):
        if e["persona"] in excluir:
            continue
        s = difflib.SequenceMatcher(None, objetivo, _normalizar(e["Respuesta"])).ratio()
        if s > mejor:
            mejor, ejemplo = s, e
    if ejemplo is None or mejor < umbral:
        return mejor, None
    return mejor, dict(ejemplo)


def bloque_fewshot(numero, k: int = 8, genero: str = "", excluir_respuesta: str = "",
                   excluir_personas=(), modo: str = "proporcional") -> str:
    ejemplos = ejemplos_para(numero, k, genero, excluir_respuesta, excluir_personas, modo)
    if not ejemplos:
        return ""
    lineas = ["Ejemplos ya clasificados por psicólogos para este mismo enunciado:"]
    lineas += [f'- "{e["Frase"]}" → {e["Categoria"]}' for e in ejemplos]
    return "\n".join(lineas) + "\n"
