#!/bin/bash
# Descarga las voces neuronales de Piper (lectura en voz alta). Solo se necesita una vez y con internet.
# Fuente: https://huggingface.co/rhasspy/piper-voices (licencias en cada MODEL_CARD).
cd "$(dirname "$0")" || exit 1
mkdir -p data/voces
BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/es"
for ruta in "es_MX/claude/high/es_MX-claude-high" "es_ES/sharvard/medium/es_ES-sharvard-medium"; do
  nombre="$(basename "$ruta")"
  for ext in onnx onnx.json; do
    if [ ! -s "data/voces/$nombre.$ext" ]; then
      echo "Descargando $nombre.$ext…"
      curl -fL --retry 2 -o "data/voces/$nombre.$ext" "$BASE/$ruta.$ext" || { rm -f "data/voces/$nombre.$ext"; echo "No se pudo descargar $nombre.$ext (la app usará la voz del sistema)."; }
    fi
  done
done
