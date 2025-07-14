from flask import request, render_template
import subprocess
import pandas as pd
from datetime import datetime
import os

PROCESSED_FOLDER = "processed"

def extraer_respuesta(output):
    res = {"categoria": "", "razon": ""}
    lines = output.strip().split("\n")

    for line in lines:
        if "Clasificación emocional:" in line:
            res["categoria"] = line.split("Clasificación emocional:")[-1].strip()
        elif line.startswith("Razón:"):
            res["razon"] = line.split("Razón:")[-1].strip()

    return res

def register_routes(app):
    @app.route("/clasificar_individual", methods=["POST"])
    def clasificar_individual():
        edad = request.form.get("edad", "")
        sexo = request.form.get("sexo", "")
        frase = request.form.get("frase", "").strip()

        if not frase:
            return render_template("resultados.html", tabla="<p>No se ingresó una frase.</p>", archivo=None)

        r = subprocess.run(
            ["ollama", "run", "deepseek-r1-sacks", frase],
            stdout=subprocess.PIPE, text=True
        )
        parsed = extraer_respuesta(r.stdout)

        resultado = pd.DataFrame([{
            "Edad": edad,
            "Sexo": sexo,
            "Frase": frase,
            "Categoria": parsed["categoria"],
            "Razon": parsed["razon"]
        }])

        out_name = f"resultado_individual_{datetime.now():%Y%m%d_%H%M%S}.csv"
        resultado.to_csv(os.path.join(PROCESSED_FOLDER, out_name), index=False, encoding="utf-8-sig")

        return render_template("resultados.html",
                               tabla=resultado.to_html(index=False),
                               archivo=out_name)