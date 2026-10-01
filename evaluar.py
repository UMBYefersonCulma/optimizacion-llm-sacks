"""Evaluación del clasificador contra las etiquetas de los psicólogos (personas no vistas).

Uso:  .venv/bin/python evaluar.py [n=150] [semilla=2026] [salida.json]
Cifras de la sustentación: semilla 2026 → 72 %, semilla 7 → 75 % (n = 150 cada una).

Para cada persona de prueba se excluyen sus respuestas de los ejemplos few-shot y de la memoria de casos,
así el modelo nunca ve la respuesta que está clasificando ni otras de la misma persona.
"""
import json, os, random, sys, time
from collections import Counter

PROY = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROY)
os.chdir(PROY)
import sacks_llm, sacks_ejemplos, sacks_items  # noqa: E402
import csv  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 150
SEMILLA = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
SALIDA = sys.argv[3] if len(sys.argv) > 3 else os.path.join(PROY, "processed", f"evaluacion_n{N}_semilla{SEMILLA}.json")

filas = []
with open("data/ejemplos_psicologos.csv", encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        cat = sacks_llm.normalizar_categoria(r["Categoria"])
        if cat in sacks_llm.CATEGORIAS and (r["Respuesta"] or "").strip():
            r["Categoria"] = cat
            filas.append(r)

rnd = random.Random(SEMILLA)
personas = sorted({r["persona"] for r in filas}, key=lambda x: int(x) if x.isdigit() else x)
prueba = set(rnd.sample(personas, 12))
prueba_int = {int(x) for x in prueba}  # sacks_ejemplos guarda la persona como int
candidatas = [r for r in filas if r["persona"] in prueba]
muestra = rnd.sample(candidatas, min(N, len(candidatas)))

resultados = []
inicio_total = time.time()
for i, r in enumerate(muestra, 1):
    numero = int(r["Numero"])
    frase = sacks_items.frase_completa(numero, r["Respuesta"], r["Genero"])
    t0 = time.time()
    sim, caso = sacks_ejemplos.vecino_mas_cercano(numero, r["Respuesta"], sacks_llm.UMBRAL_CASOS, excluir_personas=prueba_int)
    if caso:
        pred, fuente, raw = caso["Categoria"], "casos", ""
    else:
        fewshot = sacks_ejemplos.bloque_fewshot(numero, sacks_llm.FEWSHOT, r["Genero"], r["Respuesta"], excluir_personas=prueba_int)
        msg = (fewshot + "\n" if fewshot else "") + f"Edad: {r['Edad']}\nGénero: {r['Genero']}\nFrase: {frase}"
        try:
            raw, _ = sacks_llm._peticion_modelo(msg, 180)
            pred = sacks_llm.extraer_respuesta(raw)["categoria"] or "ERROR"
        except Exception as e:  # noqa: BLE001
            raw, pred = str(e), "ERROR"
        fuente = "modelo"
    dur = time.time() - t0
    resultados.append({"persona": r["persona"], "numero": numero, "frase": frase, "humano": r["Categoria"],
                       "ia": pred, "fuente": fuente, "seg": round(dur, 2)})
    ok = sum(x["humano"] == x["ia"] for x in resultados)
    print(f"[{i}/{len(muestra)}] {pred:8} vs {r['Categoria']:8} {fuente:6} {dur:5.1f}s  acc={ok/i:.1%}  | {frase[:70]}", flush=True)

cats = list(sacks_llm.CATEGORIAS)
matriz = {h: {p: 0 for p in cats + ["ERROR"]} for h in cats}
for x in resultados:
    matriz[x["humano"]][x["ia"] if x["ia"] in cats else "ERROR"] += 1
por_clase = {}
for c in cats:
    tp = matriz[c][c]
    pred_c = sum(matriz[h][c] for h in cats)
    real_c = sum(matriz[c].values())
    p = tp / pred_c if pred_c else 0
    rc = tp / real_c if real_c else 0
    por_clase[c] = {"precision": round(p, 3), "recall": round(rc, 3),
                    "f1": round(2 * p * rc / (p + rc), 3) if p + rc else 0, "soporte": real_c}
acc = sum(x["humano"] == x["ia"] for x in resultados) / len(resultados)
modelo = [x for x in resultados if x["fuente"] == "modelo"]
casos = [x for x in resultados if x["fuente"] == "casos"]
segs = sorted(x["seg"] for x in modelo)
resumen = {
    "n": len(resultados), "personas_prueba": sorted(prueba), "semilla": SEMILLA,
    "exactitud": round(acc, 3),
    "macro_f1": round(sum(v["f1"] for v in por_clase.values()) / len(cats), 3),
    "por_clase": por_clase, "matriz": matriz,
    "distribucion_humano": Counter(x["humano"] for x in resultados),
    "casos": {"n": len(casos), "acierto": round(sum(x["humano"] == x["ia"] for x in casos) / len(casos), 3) if casos else None},
    "modelo": {"n": len(modelo), "acierto": round(sum(x["humano"] == x["ia"] for x in modelo) / len(modelo), 3) if modelo else None,
               "seg_mediana": segs[len(segs) // 2] if segs else None,
               "seg_p90": segs[int(len(segs) * 0.9)] if segs else None},
    "duracion_total_s": round(time.time() - inicio_total, 1),
    "detalle": resultados,
}
with open(SALIDA, "w", encoding="utf-8") as f:
    json.dump(resumen, f, ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in resumen.items() if k != "detalle"}, ensure_ascii=False, indent=1))
