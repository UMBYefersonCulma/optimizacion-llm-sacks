from flask import Flask, request, send_file
import pandas as pd
import subprocess, os
from datetime import datetime

# ----- función para limpiar la salida del modelo -----
def extraer_respuesta(salida):
    res = {"categoria": "", "razon": ""}
    for line in salida.strip().splitlines():
        if line.startswith("Clasificación emocional:"):
            res["categoria"] = line.replace("Clasificación emocional:", "").strip()
        elif line.startswith("Razón:"):
            res["razon"] = line.replace("Razón:", "").strip()
    return res

# ----- prompt en memoria -----
PROMPT_TEMPLATE = """Eres DeepSeek-R1, un experto en análisis psicológico y lingüístico en idioma español. Todas las frases que analizarás están escritas en español coloquial dentro del contexto del Test de Frases Incompletas de Sacks.

Tu tarea es clasificar cada frase según su carga emocional en una de estas categorías exclusivas:
- POSITIVA  : emociones constructivas, afecto, esperanza, satisfacción.
- NEGATIVA  : conflicto, frustración, miedo, tristeza, enojo, rechazo.
- AMBIGUA   : contradicción, sarcasmo, ironía o vaguedad que impide determinar valencia.
- NEUTRA    : descripción informativa sin emoción clara.

Pautas clave  
1. Evalúa la frase completa; conectores como «pero», «aunque», «sin embargo» suelen introducir conflicto y pueden volverla NEGATIVA.  
2. No interpretes clínicamente ni modifiques la frase.  
3. Responde **exclusivamente** en español, sin bloques <think> ni explicaciones adicionales.  
4. Usa el formato exacto indicado más abajo.

Ejemplos (guía):

Frase: "Trata mal"  
Clasificación emocional: NEGATIVA  
Razón: Expresa maltrato y hostilidad.

Frase: "Me ayudó"  
Clasificación emocional: POSITIVA  
Razón: Denota apoyo desinteresado.

Frase: "No me escucha"  
Clasificación emocional: NEGATIVA  
Razón: Refleja frustración por falta de atención.

Frase: "Le gusta cocinar"  
Clasificación emocional: NEUTRA  
Razón: Solo describe un gusto, sin emoción.

Frase: "Me alegra estudiar, pero a veces dudo de lograrlo"  
Clasificación emocional: AMBIGUA  
Razón: Combina alegría inicial con duda que crea ambivalencia.

Frase: "Mi padre confía plenamente en mí"  
Clasificación emocional: POSITIVA  
Razón: Expresa aceptación y respaldo paterno.

Frase: "Odio fracasar"  
Clasificación emocional: NEGATIVA  
Razón: Manifiesta aversión y temor al fracaso.

Frase: "Me da igual lo que piensen"  
Clasificación emocional: NEUTRA  
Razón: Indiferencia sin carga positiva ni negativa.

Frase: "Disfruto ayudar a los demás"  
Clasificación emocional: POSITIVA  
Razón: Muestra satisfacción y altruismo.

Frase: "Me siento incomprendido"  
Clasificación emocional: NEGATIVA  
Razón: Revela sentimiento de aislamiento emocional.

Frase: "Tal vez funcione, tal vez no"  
Clasificación emocional: AMBIGUA  
Razón: Incertidumbre sin valencia clara.

Formato de respuesta (obligatorio):

Frase: <FRASE>  
Clasificación emocional: <POSITIVA / NEGATIVA / AMBIGUA / NEUTRA>  
Razón: <breve explicación: 1–2 líneas>

Responde SOLO con el formato solicitado.  
No incluyas bloques <think> ni explicaciones internas.  

Ahora analiza la siguiente frase:
Frase: "{frase}"
"""

app = Flask(__name__)
PROCESSED_FOLDER = "processed"
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

@app.route("/procesar_csv", methods=["GET", "POST"])
def procesar_csv():
    if request.method == "POST":
        file = request.files["archivo"]
        if file and file.filename.endswith(".csv"):
            df = pd.read_csv(file)
            resultados = []

            for _, row in df.iterrows():
                frase = row["Frase"]
                sexo  = row["Sexo"]
                edad  = row["Edad"]

                prompt = PROMPT_TEMPLATE.format(frase=frase)
                r = subprocess.run(
                    ["ollama", "run", "deepseek-r1:7b", prompt],
                    stdout=subprocess.PIPE, text=True
                )
                parsed = extraer_respuesta(r.stdout)
                resultados.append({
                    "Edad"     : edad,
                    "Sexo"     : sexo,
                    "Frase"    : frase,
                    "Categoria": parsed["categoria"],
                    "Razón"    : parsed["razon"]
                })

            df_out = pd.DataFrame(resultados)
            out_path = os.path.join(
                PROCESSED_FOLDER, f"resultado_{datetime.now():%Y%m%d_%H%M%S}.csv"
            )
            df_out.to_csv(out_path, index=False)

            return (
                f"<h2>Resultados</h2>{df_out.to_html(index=False)}"
                f'<br><a href="/procesar_csv">Subir otro</a>'
                f'<br><a href="/descargar?file={os.path.basename(out_path)}">Descargar CSV</a>'
            )

    # formulario
    return """
    <html><head><link rel='stylesheet' href='/static/style.css'></head><body>
    <div class='container'>
      <h2>Sube un CSV con columnas “Edad”, “Sexo”, “Frase”</h2>
      <form method='post' enctype='multipart/form-data' onsubmit='return wait()'>
        <input type='file' name='archivo' required><input type='submit' value='Procesar'>
      </form>
      <div id='wait' style='display:none;text-align:center;'>
        <img src='https://i.gifer.com/ZZ5H.gif' width='60'><br>Procesando…
      </div>
      <script>function wait(){document.querySelector('form').style.display='none';
      document.getElementById('wait').style.display='block';return true;}</script>
    </div></body></html>
    """

@app.route("/descargar")
def descargar():
    fname = request.args.get("file")
    return send_file(os.path.join(PROCESSED_FOLDER, fname), as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)