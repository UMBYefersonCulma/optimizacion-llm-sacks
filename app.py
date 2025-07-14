from flask import Flask, request, send_file, render_template, redirect, url_for
import pandas as pd
import subprocess, os
from datetime import datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import io, base64
from clasificacion_individual import register_routes


app = Flask(__name__)
register_routes(app)
PROCESSED_FOLDER = "processed"
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

resultados_comparacion_html = ""
archivo_comparacion = ""

# ─── FUNCIÓN PARA EXTRAER RESPUESTA DE OLLAMA ─── #
def extraer_respuesta(salida: str) -> dict:
    res = {"categoria": "", "razon": ""}
    for line in salida.strip().splitlines():
        if line.startswith("Clasificación emocional:"):
            res["categoria"] = line.replace("Clasificación emocional:", "").strip()
        elif line.startswith("Razón:"):
            res["razon"] = line.replace("Razón:", "").strip()
    return res

# ─── FUNCIÓN PARA NORMALIZAR LA CATEGORIAS ─── #
def normalizar_categoria(valor):
    valor = str(valor).strip().lower()
    if valor in ["positivo", "positiva"]:
        return "positivo"
    elif valor in ["negativo", "negativa"]:
        return "negativo"
    elif valor in ["ambiguo", "ambigua"]:
        return "ambiguo"
    else:
        return valor
# ─── RUTA PRINCIPAL ─── #
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/procesar_csv", methods=["GET", "POST"])
def procesar_csv():
    if request.method == "GET":
        return render_template("procesar_csv.html")

    archivo = request.files["archivo"]
    df = pd.read_csv(archivo)
    resultados = []

    for _, row in df.iterrows():
        frase = row["Frase"]
        edad = row["Edad"]
        sexo = row["Sexo"]

        r = subprocess.run(["ollama", "run", "deepseek-r1-sacks", frase], stdout=subprocess.PIPE, text=True)
        parsed = extraer_respuesta(r.stdout)

        resultados.append({
            "Edad": edad,
            "Sexo": sexo,
            "Frase": frase,
            "Categoria": parsed["categoria"],
            "Razon": parsed["razon"]
        })

    resultado_df = pd.DataFrame(resultados)
    out_name = f"resultado_{datetime.now():%Y%m%d_%H%M%S}.csv"
    resultado_df.to_csv(os.path.join(PROCESSED_FOLDER, out_name), index=False, encoding="utf-8-sig")

    return render_template("resultados.html", tabla=resultado_df.to_html(index=False), archivo_nombre=out_name)

# ─── RUTA PARA COMPARAR CSVs ─── #
@app.route("/comparar_resultados", methods=["GET", "POST"])
def comparar_resultados():
    global resultados_comparacion_html, archivo_comparacion

    if request.method == "GET":
        return render_template("comparar_resultados.html")

    humano = pd.read_csv(request.files["archivo_humano"])
    ia = pd.read_csv(request.files["archivo_ia"])

    humano.columns = [col.lower() for col in humano.columns]
    ia.columns = [col.lower() for col in ia.columns]

    ia.rename(columns={"categoria": "Categoria_IA"}, inplace=True)

    if "categoria" in humano.columns:
        humano["categoria"] = humano["categoria"].apply(normalizar_categoria)
    else:
        return "El archivo humano no contiene una columna válida de categorías.", 400

    comparado = humano.copy()
    comparado["Categoria_IA"] = ia["Categoria_IA"]
    comparado["Coincide"] = comparado.apply(
        lambda row: normalizar_categoria(row["Categoria_IA"]) == row["categoria"],
        axis=1
    )

    archivo_comparacion = os.path.join(PROCESSED_FOLDER, f"comparacion_{datetime.now():%Y%m%d_%H%M%S}.csv")
    comparado.to_csv(archivo_comparacion, index=False, encoding="utf-8-sig")
    resultados_comparacion_html = comparado.to_html(classes="styled-table", index=False)
    return redirect(url_for("ver_resultados_comparacion"))

# ─── RUTA PARA MOSTRAR RESULTADOS DE LA COMPARACIÓN ─── #
@app.route("/ver_resultados_comparacion")
def ver_resultados_comparacion():
    return render_template("resultados.html", tabla=resultados_comparacion_html, archivo_nombre=os.path.basename(archivo_comparacion))

# ─── RUTA PARA DESCARGAR ARCHIVOS ─── #
@app.route("/descargar")
def descargar():
    fname = request.args.get("file")
    return send_file(os.path.join(PROCESSED_FOLDER, fname), as_attachment=True)

# ─── MAIN ─── #
if __name__ == "__main__":
    app.run(debug=True)
