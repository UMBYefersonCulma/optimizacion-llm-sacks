"""
Frases de Sacks · Análisis emocional con DeepSeek-R1 (local, vía Ollama)
Universidad Manuela Beltrán · Práctica Empresarial II · Yeferson Culma

Flujos:
  1. Aplicar el test (3 pasos): datos generales → las frases una a una → resultados.
     Cada respuesta se analiza en segundo plano mientras la persona escribe la siguiente.
  2. Procesar un CSV de respuestas (Numero + Respuesta, o Frase completa).
  3. Comparar la clasificación de la IA contra la evaluación humana.
"""

from __future__ import annotations

import io
import os
import queue
import re
import threading
import traceback
import unicodedata
import uuid
import webbrowser
from datetime import datetime

import pandas as pd
from flask import (Flask, abort, jsonify, redirect, render_template, request,
                   send_from_directory, url_for)
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

import sacks_items
import sacks_llm
import sacks_tts

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROCESSED_FOLDER = os.path.join(BASE_DIR, "processed")
EJEMPLOS_FOLDER = os.path.join(BASE_DIR, "static", "ejemplos")
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024  # 5 MB por archivo
app.config["JSON_AS_ASCII"] = False
app.config["TEMPLATES_AUTO_RELOAD"] = True

CATEGORIAS = list(sacks_llm.CATEGORIAS)
PUERTO = int(os.environ.get("SACKS_PORT", "5050"))  # 5000 lo ocupa AirPlay en macOS
COLUMNAS_SALIDA = ["Numero", "Enunciado", "Respuesta", "Frase", "Edad", "Genero", "Categoria", "Razon", "Fuente"]
SEG_POR_FRASE = 5  # estimación inicial (mediana medida ≈ 3,5 s); se ajusta con las duraciones reales

# Modos del test: cuántos enunciados se aplican (los primeros N, como en la referencia de la Práctica III)
MODOS = {
    "demo": {"nombre": "Demo", "total": 4, "descripcion": "Rápido, ideal para una demostración"},
    "equilibrio": {"nombre": "Equilibrio", "total": 10, "descripcion": "Una muestra representativa"},
    "completo": {"nombre": "Completo", "total": 60, "descripcion": "El test completo de 60 frases"},
}

# Resultados en memoria (suficiente para una demo local; se persisten además como CSV)
JOBS: dict[str, dict] = {}
COMPARACIONES: dict[str, dict] = {}


class DatosInvalidos(Exception):
    """El archivo o formulario no tiene el formato esperado. Se muestra como página amigable (400)."""


# ───────────────────────── lectura tolerante de CSV ───────────────────────── #

ALIAS_COLUMNAS = {
    "Numero": ["numero", "num", "n", "no", "item", "pregunta", "enunciado n", "id"],
    "Respuesta": ["respuesta", "respuestas", "complemento", "completacion", "terminacion", "final"],
    "Enunciado": ["enunciado", "inicio", "frase incompleta", "stem"],
    "Frase": ["frase", "frases", "frase completada", "frase completa", "texto", "oracion", "sentence"],
    "Edad": ["edad", "age", "anos", "años"],
    "Genero": ["genero", "sexo", "sex", "gender"],
    "Categoria": ["categoria", "clasificacion", "clasificacion emocional", "categoria esperada",
                  "label", "etiqueta", "valencia", "carga emocional"],
    "Categoria_Humano": ["categoria humano", "categoria humana", "clasificacion humana", "evaluacion humana",
                         "categoria psicologo", "humano"],
    "Categoria_IA": ["categoria ia", "clasificacion ia", "categoria modelo", "ia", "categoria deepseek"],
    "Razon": ["razon", "explicacion", "justificacion", "razon ia"],
}


def _clave(texto: str) -> str:
    """Normaliza un nombre de columna o una frase para comparar: sin BOM, acentos, mayúsculas ni puntuación."""
    texto = str(texto).replace("﻿", "")
    texto = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9]+", " ", texto.lower())
    return re.sub(r"\s+", " ", texto).strip()


def leer_csv(archivo) -> pd.DataFrame:
    """Lee un CSV subido tolerando BOM, cp1252/latin-1 y separador ; o tab."""
    if archivo is None or not archivo.filename:
        raise DatosInvalidos("No se seleccionó ningún archivo.")
    nombre = archivo.filename.lower()
    if nombre.endswith((".xlsx", ".xls")):
        raise DatosInvalidos("El archivo es de Excel. Guárdalo como CSV (UTF-8) y vuelve a subirlo.")

    crudo = archivo.read()
    if not crudo.strip():
        raise DatosInvalidos(f"El archivo «{archivo.filename}» está vacío.")

    texto = None
    for codificacion in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            texto = crudo.decode(codificacion)
            break
        except UnicodeDecodeError:
            continue
    if texto is None:
        raise DatosInvalidos("No se pudo leer el archivo: codificación desconocida.")

    try:
        df = pd.read_csv(io.StringIO(texto), sep=None, engine="python")
    except Exception:  # noqa: BLE001 — el sniffer falla con una sola columna; reintentar con coma
        try:
            df = pd.read_csv(io.StringIO(texto))
        except Exception as e:  # noqa: BLE001
            raise DatosInvalidos(f"No se pudo interpretar «{archivo.filename}» como CSV: {e}") from e

    if df.empty or len(df.columns) == 0:
        raise DatosInvalidos(f"El archivo «{archivo.filename}» no contiene filas de datos.")

    df.columns = [str(c).replace("﻿", "").strip() for c in df.columns]
    return estandarizar_columnas(df)


def estandarizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    """Renombra columnas equivalentes (Frase/frase/Texto, Sexo/Género…) a los nombres canónicos."""
    renombres = {}
    usados = set()
    for col in df.columns:
        clave = _clave(col)
        for canonico, alias in ALIAS_COLUMNAS.items():
            if canonico in usados:
                continue
            if clave == _clave(canonico) or clave in alias:
                renombres[col] = canonico
                usados.add(canonico)
                break
    return df.rename(columns=renombres)


def _texto(valor) -> str:
    return "" if pd.isna(valor) else str(valor).strip()


def _limpiar_edad(valor):
    if valor is None or pd.isna(valor):
        return ""
    try:
        return str(int(float(valor)))
    except (TypeError, ValueError):
        return str(valor).strip()


def _limpiar_genero(valor):
    if valor is None or pd.isna(valor):
        return ""
    texto = str(valor).strip().strip(".").strip()
    clave = _clave(texto)
    if clave in ("m", "h", "masc", "masculino", "hombre", "varon", "male"):
        return "Masculino"
    if clave in ("f", "fem", "femenino", "mujer", "female"):
        return "Femenino"
    if clave in ("x", "o", "otro", "otra", "no binario", "prefiero no decir", "prefiero no decirlo", "ns", "nr"):
        return "Otro"
    return texto


def _limpiar_numero(valor):
    try:
        n = int(float(valor))
        return n if n in sacks_items.AREA_DE_ITEM else ""
    except (TypeError, ValueError):
        return ""


def preparar_filas(df: pd.DataFrame, nombre_archivo: str) -> list[dict]:
    """
    Convierte un CSV en filas listas para el modelo. Acepta dos formatos:
      - Numero + Respuesta (la app une el enunciado de Sacks con la respuesta), o
      - Frase completa.
    Edad y Genero son opcionales.
    """
    tiene_numero = "Numero" in df.columns and "Respuesta" in df.columns
    if not tiene_numero and "Frase" not in df.columns and "Respuesta" in df.columns:
        df = df.rename(columns={"Respuesta": "Frase"})
    if not tiene_numero and "Frase" not in df.columns:
        raise DatosInvalidos(
            f"El archivo «{nombre_archivo}» no tiene las columnas esperadas. "
            f"Columnas encontradas: {', '.join(map(str, df.columns))}. "
            "Se espera «Numero, Respuesta» (número del enunciado de Sacks y lo que escribió la persona) "
            "o «Frase» con la frase completa. Edad y Genero son opcionales."
        )

    filas = []
    for _, r in df.iterrows():
        edad = _limpiar_edad(r["Edad"]) if "Edad" in df.columns else ""
        genero = _limpiar_genero(r["Genero"]) if "Genero" in df.columns else ""
        if tiene_numero:
            numero = _limpiar_numero(r["Numero"])
            respuesta = _texto(r["Respuesta"])
            if numero == "" or not respuesta:
                continue
            enunciado = sacks_items.enunciado(numero, genero)
            frase = sacks_items.frase_completa(numero, respuesta, genero)
        else:
            numero, enunciado, respuesta = "", "", ""
            frase = _texto(r["Frase"])
            if not frase:
                continue
        filas.append({"Numero": numero, "Enunciado": enunciado, "Respuesta": respuesta,
                      "Frase": frase, "Edad": edad, "Genero": genero})

    if not filas:
        raise DatosInvalidos(f"El archivo «{nombre_archivo}» no tiene respuestas para analizar.")
    return filas


def columna_categoria(df: pd.DataFrame, preferida: str) -> str | None:
    """Elige la columna de categorías de un archivo: la preferida (Humano/IA) o la genérica."""
    for candidata in (preferida, "Categoria", "Categoria_Humano", "Categoria_IA"):
        if candidata in df.columns:
            return candidata
    return None


# ───────────────────────── helpers de presentación ───────────────────────── #

def distribucion(categorias) -> list[dict]:
    serie = pd.Series([c for c in categorias if c in CATEGORIAS], dtype="object")
    total = int(len(serie))
    filas = []
    for cat in CATEGORIAS:
        n = int((serie == cat).sum())
        filas.append({"categoria": cat, "n": n, "pct": round(100 * n / total, 1) if total else 0.0})
    return filas


def resumen_areas(filas: list[dict]) -> list[dict]:
    """Agrupa las respuestas analizadas por las 15 áreas del SSCT."""
    por_numero = {f["Numero"]: f for f in filas if f.get("Numero") != ""}
    salida = []
    for romano, nombre, numeros in sacks_items.AREAS:
        respuestas = [por_numero[n] for n in numeros if n in por_numero]
        # OJO: no usar la clave "items": Jinja la confundiría con el método dict.items
        salida.append({
            "romano": romano, "nombre": nombre, "numeros": numeros, "respuestas": respuestas,
            "n": len(respuestas), "dist": distribucion(f["Categoria"] for f in respuestas),
            "negativas": sum(1 for f in respuestas if f["Categoria"] == "NEGATIVA"),
        })
    return salida


def guardar_csv(df: pd.DataFrame, prefijo: str) -> str:
    nombre = f"{prefijo}_{datetime.now():%Y%m%d_%H%M%S}.csv"
    df.to_csv(os.path.join(PROCESSED_FOLDER, nombre), index=False, encoding="utf-8-sig")
    return nombre


def _clasificar_fila(job: dict, fila: dict) -> dict | None:
    """Clasifica una fila con el modelo. Devuelve el registro, o None si Ollama está caído (job en error)."""
    registro = dict(fila)
    try:
        r = sacks_llm.clasificar(fila["Frase"], fila["Edad"], fila["Genero"],
                                 numero=fila.get("Numero"), respuesta=fila.get("Respuesta", ""))
        registro.update(Categoria=r.categoria, Razon=r.razon, Duracion_s=r.duracion_s, Fuente=r.fuente)
        if r.fuente == "modelo":
            job["duraciones"].append(r.duracion_s)
    except sacks_llm.LLMError as e:
        mensaje = str(e)
        if "No se pudo conectar" in mensaje or "no está instalado" in mensaje:
            job.update(estado="error", error=mensaje)
            return None
        registro.update(Categoria="ERROR", Razon=mensaje, Duracion_s=None, Fuente="")
        job["errores"] += 1
    area = sacks_items.area_de(registro["Numero"]) if registro["Numero"] != "" else None
    registro["Area"] = f"{area[0]}. {area[1]}" if area else ""
    return registro


def _cerrar_job(job: dict) -> None:
    if job["filas"]:
        salida = pd.DataFrame(job["filas"])[COLUMNAS_SALIDA + ["Area"]]
        job["archivo"] = guardar_csv(salida, "resultado_test" if job["tipo"] == "test" else "resultado")
    job["fin"] = datetime.now()
    job["estado"] = "listo"


def _nuevo_job(tipo: str, nombre_entrada: str, total: int, **extra) -> dict:
    job_id = uuid.uuid4().hex[:8]
    job = {
        "id": job_id, "tipo": tipo, "estado": "en_cola", "total": total, "hechas": 0, "errores": 0,
        "filas": [], "ultima": None, "archivo": None, "error": None, "duraciones": [],
        "nombre_entrada": nombre_entrada, "inicio": datetime.now(), "fin": None, **extra,
    }
    JOBS[job_id] = job
    return job


@app.context_processor
def _globales():
    return {"CATEGORIAS": CATEGORIAS, "MODELO": sacks_llm.MODELO, "MODOS": MODOS}


# ───────────────────────── 1. aplicar el test (3 pasos) ───────────────────────── #

def _worker_test(job_id: str) -> None:
    """Clasifica las respuestas a medida que llegan; al finalizar el test cierra el job."""
    job = JOBS[job_id]
    while True:
        try:
            n = job["cola"].get(timeout=1.0)
        except queue.Empty:
            if job["finalizado"] and job["cola"].empty():
                break
            continue
        respuesta = job["respuestas"].get(n, "")
        if not respuesta or job["estado"] == "error":
            continue
        fila = {"Numero": n, "Enunciado": sacks_items.enunciado(n, job["genero"]), "Respuesta": respuesta,
                "Frase": sacks_items.frase_completa(n, respuesta, job["genero"]),
                "Edad": job["edad"], "Genero": job["genero"]}
        registro = _clasificar_fila(job, fila)
        if registro is None:
            return
        if job["respuestas"].get(n) != respuesta:
            continue  # la persona cambió la respuesta mientras se analizaba; ya hay una nueva en cola
        job["resultados"][n] = registro
        job["hechas"] = len(job["resultados"])
        job["ultima"] = registro
    job["filas"] = [job["resultados"][n] for n in job["numeros"] if n in job["resultados"]]
    _cerrar_job(job)


@app.route("/")
def index():
    return render_template("test_inicio.html")


@app.route("/test/iniciar", methods=["POST"])
def iniciar_test():
    edad = _limpiar_edad(request.form.get("edad", "").strip() or None)
    genero = _limpiar_genero(request.form.get("genero", "").strip() or None)
    modo = request.form.get("modo", "completo")
    if not edad or not edad.isdigit() or not (5 <= int(edad) <= 110):
        raise DatosInvalidos("Indica una edad válida (entre 5 y 110 años).")
    if genero not in ("Femenino", "Masculino", "Otro"):
        raise DatosInvalidos("Selecciona un género.")
    if modo not in MODOS:
        raise DatosInvalidos("Selecciona un modo del test.")

    numeros = sacks_items.NUMEROS[:MODOS[modo]["total"]]
    job = _nuevo_job("test", "Test de Sacks", len(numeros), edad=edad, genero=genero, modo=modo,
                     numeros=numeros, respuestas={}, resultados={}, cola=queue.Queue(), finalizado=False)
    job["estado"] = "respondiendo"
    threading.Thread(target=_worker_test, args=(job["id"],), daemon=True, name=f"test-{job['id']}").start()
    return redirect(url_for("responder_test", job_id=job["id"]))


def _job_test_o_404(job_id: str) -> dict:
    job = JOBS.get(job_id)
    if not job or job["tipo"] != "test":
        abort(404)
    return job


@app.route("/test/<job_id>")
def responder_test(job_id):
    job = _job_test_o_404(job_id)
    if job["estado"] in ("procesando", "listo"):
        return redirect(url_for("progreso", job_id=job_id))
    if job["estado"] == "error":
        raise sacks_llm.LLMError(job["error"])
    preguntas = [{"numero": n, "enunciado": sacks_items.enunciado(n, job["genero"]),
                  "respuesta": job["respuestas"].get(n, "")} for n in job["numeros"]]
    return render_template("test.html", job=job, preguntas=preguntas, modo=MODOS[job["modo"]])


@app.route("/api/test/<job_id>/respuesta", methods=["POST"])
def api_respuesta(job_id):
    job = _job_test_o_404(job_id)
    datos = request.get_json(silent=True) or {}
    try:
        n = int(datos.get("numero"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Número inválido."}), 400
    if n not in job["numeros"]:
        return jsonify({"ok": False, "error": "Ese enunciado no pertenece a este test."}), 400
    if job["estado"] != "respondiendo":
        return jsonify({"ok": False, "error": "El test ya fue enviado a análisis."}), 409

    respuesta = (datos.get("respuesta") or "").strip()[:300]
    anterior = job["respuestas"].get(n, "")
    if respuesta != anterior:
        job["resultados"].pop(n, None)
        job["hechas"] = len(job["resultados"])
        if respuesta:
            job["respuestas"][n] = respuesta
            job["cola"].put(n)
        else:
            job["respuestas"].pop(n, None)
    return jsonify({"ok": True, "respondidas": len(job["respuestas"]), "analizadas": job["hechas"],
                    "total": job["total"]})


@app.route("/test/<job_id>/finalizar", methods=["POST"])
def finalizar_test(job_id):
    job = _job_test_o_404(job_id)
    if job["estado"] == "respondiendo":
        faltan = [n for n in job["numeros"] if not job["respuestas"].get(n)]
        if faltan:
            raise DatosInvalidos("Faltan por responder las frases: " + ", ".join(map(str, faltan)) +
                                 ". Todas las frases del test deben completarse.")
        job["finalizado"] = True
        job["estado"] = "procesando"
    return redirect(url_for("progreso", job_id=job_id))


# ───────────────────────── 2. procesar CSV en segundo plano ───────────────────────── #

def _procesar_lote(job_id: str, filas: list[dict]) -> None:
    job = JOBS[job_id]
    job["estado"] = "procesando"
    for fila in filas:
        registro = _clasificar_fila(job, fila)
        if registro is None:
            return
        job["filas"].append(registro)
        job["hechas"] += 1
        job["ultima"] = registro
    _cerrar_job(job)


@app.route("/procesar_csv", methods=["GET", "POST"])
def procesar_csv():
    if request.method == "GET":
        return render_template("procesar_csv.html")

    archivo = request.files.get("archivo")
    filas = preparar_filas(leer_csv(archivo), archivo.filename)
    tipo = "csv_test" if all(f["Numero"] != "" for f in filas) else "csv"
    job = _nuevo_job(tipo, archivo.filename, len(filas), edad=filas[0]["Edad"], genero=filas[0]["Genero"])
    threading.Thread(target=_procesar_lote, args=(job["id"], filas), daemon=True, name=f"csv-{job['id']}").start()
    return redirect(url_for("progreso", job_id=job["id"]))


@app.route("/progreso/<job_id>")
def progreso(job_id):
    job = JOBS.get(job_id) or abort(404)
    if job["estado"] == "listo":
        return redirect(url_for("resultados", job_id=job_id))
    if job["estado"] == "respondiendo":
        return redirect(url_for("responder_test", job_id=job_id))
    return render_template("progreso.html", job=job)


@app.route("/api/progreso/<job_id>")
def api_progreso(job_id):
    job = JOBS.get(job_id) or abort(404)
    transcurrido = (datetime.now() - job["inicio"]).total_seconds()
    if job["duraciones"]:
        promedio = sum(job["duraciones"]) / len(job["duraciones"])
    else:
        promedio = SEG_POR_FRASE
    restante = promedio * (job["total"] - job["hechas"])
    return jsonify({
        "estado": job["estado"], "total": job["total"], "hechas": job["hechas"], "errores": job["errores"],
        "ultima": job["ultima"], "error": job["error"], "transcurrido_s": round(transcurrido),
        "restante_s": round(restante),
        "url_resultados": url_for("resultados", job_id=job_id) if job["estado"] == "listo" else None,
    })


@app.route("/resultados/<job_id>")
def resultados(job_id):
    job = JOBS.get(job_id) or abort(404)
    if job["estado"] != "listo":
        return redirect(url_for("progreso", job_id=job_id))
    filas = job["filas"]
    es_test = job["tipo"] in ("test", "csv_test")
    if es_test:
        filas = sorted(filas, key=lambda f: f["Numero"])
    tiempo_modelo = round(sum(d for d in job["duraciones"]))
    return render_template(
        "resultados.html",
        job=job,
        filas=filas,
        areas=resumen_areas(filas) if es_test else [],
        dist=distribucion(f["Categoria"] for f in filas),
        tiempo_modelo=tiempo_modelo,
        promedio=round(tiempo_modelo / job["hechas"], 1) if job["hechas"] else 0,
    )


# ───────────────────────── 3. comparar IA vs humano ───────────────────────── #

def _tabla_comparacion(df: pd.DataFrame, col_cat: str, col_razon: str | None) -> pd.DataFrame:
    """Deja un archivo (humano o IA) en un formato común: Numero, Frase, Edad, Genero, Categoria, Razon."""
    genero_col = df["Genero"].map(_limpiar_genero) if "Genero" in df.columns else ""
    salida = pd.DataFrame({
        "Numero": df["Numero"].map(_limpiar_numero) if "Numero" in df.columns else "",
        "Frase": df["Frase"].map(_texto) if "Frase" in df.columns else "",
        "Edad": df["Edad"].map(_limpiar_edad) if "Edad" in df.columns else "",
        "Genero": genero_col,
        "Categoria": df[col_cat].map(sacks_llm.normalizar_categoria),
        "Razon": df[col_razon].map(_texto) if col_razon and col_razon in df.columns else "",
        "Respuesta": df["Respuesta"].map(_texto) if "Respuesta" in df.columns else "",
    })
    # Si viene Numero + Respuesta pero no Frase, construimos la frase completa.
    if "Respuesta" in df.columns and "Numero" in df.columns:
        sin_frase = salida["Frase"] == ""
        for idx in salida.index[sin_frase]:
            n = salida.at[idx, "Numero"]
            if n != "":
                salida.at[idx, "Frase"] = sacks_items.frase_completa(n, _texto(df.at[idx, "Respuesta"]),
                                                                     salida.at[idx, "Genero"])
    return salida


@app.route("/comparar_resultados", methods=["GET", "POST"])
def comparar_resultados():
    if request.method == "GET":
        return render_template("comparar_resultados.html", ia_servidor=request.args.get("ia", ""))

    archivo_humano = request.files.get("archivo_humano")
    humano = leer_csv(archivo_humano)
    nombre_humano = archivo_humano.filename

    ia_servidor = (request.form.get("archivo_ia_servidor") or "").strip()
    archivo_ia = request.files.get("archivo_ia")
    if archivo_ia is not None and archivo_ia.filename:
        ia = leer_csv(archivo_ia)
        nombre_ia = archivo_ia.filename
    elif ia_servidor:
        with open(_ruta_procesado(ia_servidor), "rb") as f:
            ia = leer_csv(FileStorage(stream=io.BytesIO(f.read()), filename=ia_servidor))
        nombre_ia = ia_servidor
    else:
        raise DatosInvalidos("Falta el archivo generado por la IA.")

    col_h = columna_categoria(humano, "Categoria_Humano")
    col_ia = columna_categoria(ia, "Categoria_IA")
    if col_h is None:
        raise DatosInvalidos(f"El archivo humano «{nombre_humano}» no tiene una columna de categorías "
                             f"(Categoria / Categoria_Humano). Columnas: {', '.join(map(str, humano.columns))}.")
    if col_ia is None:
        raise DatosInvalidos(f"El archivo de la IA «{nombre_ia}» no tiene una columna de categorías "
                             f"(Categoria / Categoria_IA). Columnas: {', '.join(map(str, ia.columns))}.")

    h = _tabla_comparacion(humano, col_h, None).rename(columns={"Categoria": "Categoria_Humano"})
    i = _tabla_comparacion(ia, col_ia, "Razon" if "Razon" in ia.columns else None) \
        .rename(columns={"Categoria": "Categoria_IA", "Razon": "Razon_IA"})

    avisos = []
    tiene_numero = (h["Numero"] != "").all() and (i["Numero"] != "").all()
    tiene_frase = (h["Frase"] != "").all() and (i["Frase"] != "").all()
    tiene_respuesta = (h["Respuesta"] != "").all() and (i["Respuesta"] != "").all()
    if tiene_numero or tiene_frase:
        # Se empareja la MISMA respuesta: número de enunciado + texto, para no cruzar personas distintas.
        if tiene_numero and tiene_respuesta:
            modo = "por enunciado y respuesta"
            h["_k"] = h["Numero"].astype(str) + "|" + h["Respuesta"].map(_clave)
            i["_k"] = i["Numero"].astype(str) + "|" + i["Respuesta"].map(_clave)
        elif tiene_numero and tiene_frase:
            modo = "por enunciado y frase"
            h["_k"] = h["Numero"].astype(str) + "|" + h["Frase"].map(_clave)
            i["_k"] = i["Numero"].astype(str) + "|" + i["Frase"].map(_clave)
        elif tiene_numero:
            modo = "por número de enunciado"
            h["_k"], i["_k"] = h["Numero"], i["Numero"]
        else:
            modo = "por frase"
            h["_k"], i["_k"] = h["Frase"].map(_clave), i["Frase"].map(_clave)
        i = i.drop_duplicates("_k")
        derecha = i[["_k", "Categoria_IA", "Razon_IA"] + (["Frase"] if (h["Frase"] == "").all() else [])]
        comparado = h.merge(derecha, on="_k", how="left", suffixes=("", "_ia")).drop(columns=["_k"])
        if "Frase_ia" in comparado.columns:
            comparado["Frase"] = comparado["Frase_ia"]
            comparado = comparado.drop(columns=["Frase_ia"])
        sin_par = int(comparado["Categoria_IA"].isna().sum())
        if sin_par == len(comparado):
            raise DatosInvalidos("Ninguna respuesta del archivo humano aparece en el archivo de la IA. Verifica que "
                                 "ambos archivos tengan las mismas respuestas (por ejemplo, respuestas_demo.csv procesado "
                                 "con «Procesar CSV» y evaluacion_humana_demo.csv).")
        if sin_par:
            avisos.append(f"{sin_par} respuesta(s) del archivo humano no aparecen con el mismo texto en el archivo "
                          "de la IA; se excluyeron del cálculo.")
            comparado = comparado[comparado["Categoria_IA"].notna()].reset_index(drop=True)
    else:
        modo = "por posición"
        if len(h) != len(i):
            avisos.append(f"Los archivos tienen distinto número de filas ({len(h)} humano vs {len(i)} IA); "
                          "se compararon por posición hasta donde coinciden.")
        n = min(len(h), len(i))
        comparado = pd.concat([h.iloc[:n].reset_index(drop=True),
                               i.iloc[:n].reset_index(drop=True)[["Categoria_IA", "Razon_IA"]]], axis=1)
        if (comparado["Frase"] == "").all():
            comparado["Frase"] = i["Frase"].iloc[:n].values

    comparado["Categoria_IA"] = comparado["Categoria_IA"].fillna("")
    comparado["Razon_IA"] = comparado["Razon_IA"].fillna("")
    comparado["Coincide"] = (comparado["Categoria_Humano"] != "") & \
                            (comparado["Categoria_Humano"] == comparado["Categoria_IA"])

    total = int(len(comparado))
    coincidencias = int(comparado["Coincide"].sum())
    porcentaje = round(100 * coincidencias / total, 1) if total else 0.0

    por_categoria = []
    for cat in CATEGORIAS:
        sub = comparado[comparado["Categoria_Humano"] == cat]
        n = int(len(sub))
        ok = int(sub["Coincide"].sum())
        por_categoria.append({"categoria": cat, "n": n, "ok": ok, "pct": round(100 * ok / n, 1) if n else None})

    matriz = []
    for cat_h in CATEGORIAS:
        fila = {"humano": cat_h, "celdas": []}
        for cat_ia in CATEGORIAS:
            fila["celdas"].append(int(((comparado["Categoria_Humano"] == cat_h) &
                                       (comparado["Categoria_IA"] == cat_ia)).sum()))
        matriz.append(fila)

    salida = comparado[["Numero", "Frase", "Edad", "Genero", "Categoria_Humano", "Categoria_IA", "Coincide", "Razon_IA"]]
    archivo = guardar_csv(salida, "comparacion")

    comp_id = uuid.uuid4().hex[:8]
    COMPARACIONES[comp_id] = {
        "id": comp_id, "archivo": archivo, "filas": salida.to_dict("records"),
        "total": total, "coincidencias": coincidencias, "porcentaje": porcentaje,
        "por_categoria": por_categoria, "matriz": matriz, "avisos": avisos, "modo": modo,
        "nombre_humano": nombre_humano, "nombre_ia": nombre_ia, "fecha": datetime.now(),
    }
    return redirect(url_for("ver_comparacion", comp_id=comp_id))


@app.route("/comparacion/<comp_id>")
def ver_comparacion(comp_id):
    comp = COMPARACIONES.get(comp_id) or abort(404)
    return render_template("comparacion.html", c=comp)


# ───────────────────────── descargas y utilidades ───────────────────────── #

def _ruta_procesado(nombre: str) -> str:
    seguro = os.path.basename(nombre or "")
    ruta = os.path.join(PROCESSED_FOLDER, seguro)
    if not seguro or not seguro.endswith(".csv") or not os.path.isfile(ruta):
        abort(404)
    return ruta


@app.route("/descargar")
def descargar():
    nombre = os.path.basename(_ruta_procesado(request.args.get("file", "")))
    return send_from_directory(PROCESSED_FOLDER, nombre, as_attachment=True)


@app.route("/ejemplos/<nombre>")
def ejemplos(nombre):
    seguro = os.path.basename(nombre)
    if not os.path.isfile(os.path.join(EJEMPLOS_FOLDER, seguro)):
        abort(404)
    return send_from_directory(EJEMPLOS_FOLDER, seguro, as_attachment=True)


@app.route("/api/estado")
def api_estado():
    estado = sacks_llm.estado_ollama()
    estado["voz"] = {"disponible": sacks_tts.disponible(), "voces": sacks_tts.voces_disponibles(),
                     "por_defecto": sacks_tts.VOZ_POR_DEFECTO}
    return jsonify(estado)


@app.route("/api/voz")
def api_voz():
    """Voz neuronal local (Piper): devuelve un WAV con el texto leído."""
    texto = (request.args.get("texto") or "").strip()
    if not texto:
        abort(400)
    if not sacks_tts.disponible():
        abort(503)
    vid = request.args.get("voz") or sacks_tts.VOZ_POR_DEFECTO
    try:
        velocidad = float(request.args.get("velocidad") or 1.0)
    except ValueError:
        velocidad = 1.0
    datos = sacks_tts.sintetizar(texto, vid, velocidad)
    resp = app.response_class(datos, mimetype="audio/wav")
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


# ───────────────────────── manejo de errores (sin traceback en pantalla) ───────────────────────── #

@app.errorhandler(DatosInvalidos)
def _error_datos(e):
    return render_template("error.html", titulo="Revisa los datos", mensaje=str(e), codigo=400), 400


@app.errorhandler(sacks_llm.LLMError)
def _error_modelo(e):
    return render_template("error.html", titulo="El modelo no respondió", mensaje=str(e), codigo=502,
                           estado=sacks_llm.estado_ollama()), 502


@app.errorhandler(RequestEntityTooLarge)
def _error_tamano(e):
    return render_template("error.html", titulo="Archivo demasiado grande",
                           mensaje="El límite es de 5 MB por archivo.", codigo=413), 413


@app.errorhandler(404)
def _error_404(e):
    return render_template("error.html", titulo="No encontrado",
                           mensaje="La página o el archivo que buscas no existe (o el servidor se reinició y el resultado ya no está en memoria).",
                           codigo=404), 404


@app.errorhandler(Exception)
def _error_general(e):
    if isinstance(e, HTTPException):
        return e
    traceback.print_exc()
    return render_template("error.html", titulo="Ocurrió un error inesperado",
                           mensaje=f"{e.__class__.__name__}: {e}", codigo=500), 500


# ───────────────────────── arranque ───────────────────────── #

def _banner():
    estado = sacks_llm.estado_ollama()
    print("\n" + "─" * 70)
    print("  Frases de Sacks · Análisis emocional con DeepSeek-R1 (local)")
    print("─" * 70)
    if not estado["ok"]:
        print(f"  ⚠  Ollama no responde en {sacks_llm.OLLAMA_BASE_URL}: {estado['error']}")
        print("     Abre la aplicación Ollama y vuelve a intentar.")
    elif not estado["modelo_presente"]:
        print(f"  ⚠  El modelo '{sacks_llm.MODELO}' NO está instalado. Modelos: {', '.join(estado['modelos'])}")
        print(f"     Ejecuta:  ollama create {sacks_llm.MODELO} -f Modelfile")
    else:
        print(f"  ✓  Ollama activo · modelo '{sacks_llm.MODELO}' listo (precalentando en segundo plano)")
        sacks_llm.precalentar()
    if sacks_tts.disponible():
        print(f"  ✓  Voz local (Piper): {', '.join(v['nombre'] for v in sacks_tts.voces_disponibles())}")
        sacks_tts.precalentar()
    else:
        print("  ·  Voz local no disponible; se usará la voz del sistema en el navegador")
    print(f"  →  http://127.0.0.1:{PUERTO}")
    print("─" * 70 + "\n")


if __name__ == "__main__":
    _banner()
    if os.environ.get("SACKS_NO_BROWSER") != "1":
        threading.Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{PUERTO}")).start()
    app.run(host="127.0.0.1", port=PUERTO, debug=os.environ.get("FLASK_DEBUG") == "1",
            use_reloader=False, threaded=True)
