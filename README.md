# Optimización de LLM para el Análisis del Test de Sacks

## Descripción

Este es un proyecto universitario de la asignatura Práctica II – UMB, cuyo objetivo es optimizar el uso de un modelo de lenguaje grande (LLM) local, específicamente **DeepSeek-R1**, para la **evaluación automatizada de respuestas al Test de Frases Incompletas de Sacks**.

El sistema permite tanto la interacción individual tipo "chat" como el análisis masivo de frases a través de archivos `.csv`, con un enfoque en privacidad, trazabilidad y clasificación emocional.

---

## Objetivos

- Configurar y ajustar un LLM para el análisis psicológico de respuestas proyectivas.
- Aplicar un metaprompt especializado para la **clasificación automática** en dimensiones emocionales: POSITIVA, NEGATIVA, AMBIGUA, NEUTRA.
- Registrar y documentar todas las interacciones con el modelo para su análisis posterior.
- Validar el desempeño del modelo frente a criterios humanos.

---

## Tecnologías utilizadas

- [Ollama](https://ollama.com) – Para ejecución local del modelo LLM.
- DeepSeek-R1:7B – Modelo de lenguaje usado.
- Python + Flask – Backend local para la interfaz.
- Pandas – Procesamiento de archivos `.csv`.
- HTML (con Flask) – Interfaz simple en navegador.
- GitHub – Repositorio del proyecto.
- OneDrive / Trello – Gestión de avances del equipo.

---

## Estructura del Repositorio

```bash
proyect/
├── app.py                  # Aplicación Flask principal
├── templates/              # HTML de la interfaz
├── static/                 # Archivos estáticos (CSS, JS)
├── uploads/                # Archivos .csv subidos para análisis masivo
├── processed/              # Archivos .csv generados con resultados
├── logs/                   # Registro automático de cada interacción
│   └── log.csv             # Formato: timestamp, frase, respuesta completa
├── requirements.txt        # Dependencias del proyecto
├── Modelfile               # (Opcional) Configuración personalizada para Ollama
└── README.md               # Este archivo

---

## Colaboradores

- **Yeferson Culma**
- **Juan Gualteros**