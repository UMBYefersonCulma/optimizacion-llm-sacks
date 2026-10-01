#!/bin/bash
# Doble clic para iniciar la demo: prepara el entorno, verifica Ollama y abre el navegador.
cd "$(dirname "$0")" || exit 1

echo "── Frases de Sacks · iniciando ──"

if [ ! -x .venv/bin/python ]; then
  echo "Creando entorno virtual…"
  python3 -m venv .venv && .venv/bin/pip install --quiet -r requirements.txt
fi

if [ ! -s data/voces/es_MX-claude-high.onnx ]; then
  echo "Descargando las voces de lectura en voz alta (solo la primera vez)…"
  ./descargar_voces.sh
fi

if ! curl -s --max-time 2 http://localhost:11434/api/tags >/dev/null; then
  echo "Ollama no responde; abriendo la aplicación…"
  open -a Ollama 2>/dev/null
  for _ in $(seq 1 20); do
    sleep 1
    curl -s --max-time 2 http://localhost:11434/api/tags >/dev/null && break
  done
fi

if ! ollama list 2>/dev/null | grep -q "^deepseek-r1-sacks"; then
  echo "El modelo deepseek-r1-sacks no existe; creándolo desde el Modelfile…"
  ollama create deepseek-r1-sacks -f Modelfile
fi

exec .venv/bin/python app.py
