# Frases de Sacks · Análisis emocional con DeepSeek-R1 (local)

Proyecto de la asignatura **Práctica Empresarial II – Universidad Manuela Beltrán** (Ingeniería de Software, 2025).
Automatiza la clasificación emocional de respuestas al **Test de Frases Incompletas de Sacks** usando un modelo de
lenguaje grande ejecutado **100 % en local** con [Ollama](https://ollama.com): privacidad total, sin costos de API y
sin enviar datos sensibles a terceros.

Cada frase se clasifica como **POSITIVA · NEGATIVA · AMBIGUA** y el modelo explica brevemente la razón. (La categoría
«neutra» del dataset original se asimila a AMBIGUA: información sin carga emocional o sin evidencia suficiente.)

## Flujos de la aplicación

| Flujo | Qué hace |
|---|---|
| **Interruptor Persona · Psicólogo** | La barra superior separa las dos vistas de la misma app, sin mezclar información. |
| **Vista de la persona** | Bienvenida corta y cuatro pasos: (1) **autorización de datos** resumida en cuatro líneas, con el detalle legal en un diálogo (Ley 1581 de 2012, Ley 1090 de 2006); sin marcar la casilla no se puede continuar y la fecha queda en el informe; (2) edad y género; (3) las frases **una a una**, con un botón **«?»** de preguntas frecuentes; (4) mensaje de cierre y acceso a los resultados para el psicólogo. Cada respuesta se analiza en segundo plano. |
| **Vista del psicólogo** | Un solo espacio con pestañas: **Aplicar test** (versión Completo 60, Equilibrio 10 o Demo 4), **Informes** de la sesión, **Procesar CSV** (`Numero, Respuesta` o `Frase`) y **Comparar con psicólogos** (concordancia, matriz de confusión y detalle, emparejando la misma respuesta). |

Los ítems 9, 10, 25, 40, 55 y 57 cambian de redacción según el género (niño/niña, sexo contrario); es el único
dato, junto con la edad, que se le pide a la persona. Todas las frases del modo elegido deben completarse. Si un
enunciado presupone algo que no corresponde a la situación de la persona (por ejemplo, «mi padre» para quien no lo
conoció), la persona lo escribe tal cual y el modelo clasifica la carga emocional de esa respuesta.

Métricas reportadas en el informe de práctica: 78 % de concordancia con evaluadores humanos, 3 a 5 s por frase en un
equipo de 8 GB sin GPU. En esta versión, en un MacBook Pro M3 Pro, cada frase tarda unos 3 s (modo rápido) y las
respuestas que coinciden con la memoria de casos se resuelven al instante.

## Arquitectura

```
Navegador ──► Flask (app.py) ──► sacks_llm.py ──HTTP──► Ollama (localhost:11434) ──► deepseek-r1-sacks
                 │                    │                                                (DeepSeek-R1 7B + system prompt
                 │                    ├── sacks_ejemplos.py  memoria de casos + few-shot     en español, temperatura 0)
                 │                    │     data/ejemplos_psicologos.csv (3061 respuestas
                 │                    │     etiquetadas por psicólogos, 52 personas × 60 ítems)
                 ├── processed/   CSV de resultados y comparaciones
                 └── logs/log.csv registro de cada clasificación
```

Cómo se clasifica cada frase (en este orden):

1. **Memoria de casos.** Si la respuesta es casi idéntica (similitud ≥ 0,85) a una ya clasificada por los
   psicólogos del proyecto para el mismo enunciado, se usa esa clasificación al instante (fuente «psicólogos»).
   Medido sobre datos no vistos acierta el 94-96 % de las veces.
2. **DeepSeek-R1 en modo rápido.** Se envía el prompt de sistema del `Modelfile` más 8 ejemplos etiquetados del
   mismo enunciado, en la proporción real en que los psicólogos usaron cada categoría, y se omite la cadena de
   razonamiento larga del modelo (≈ 3 s por frase en un M3 Pro, frente a 13-15 s con razonamiento, y con igual
   o mejor exactitud en las pruebas). `SACKS_MODO=think` vuelve al razonamiento completo.

Exactitud medida contra las etiquetas de los psicólogos con personas que el sistema no vio (ni como ejemplos ni en la
memoria de casos), con tres categorías: 72 % y 75 % en dos muestras independientes de 150 respuestas (κ de Cohen 0,55
en la primera), frente a 52 % de responder siempre la clase más frecuente y 70 % del prompt original; 16 de 17 casos de
control del proyecto correctos. POSITIVA es la categoría más fiable (F1 0,85); la mayoría de los errores son confusiones
entre AMBIGUA y NEGATIVA. Para reproducirlo: `.venv/bin/python evaluar.py 150 2026` (requiere Ollama encendido).

- **`Modelfile`**: prompt de sistema con la convención de los psicólogos (marco negativo «raras veces», violencia
  física siempre NEGATIVA, anhelo no cumplido nunca POSITIVA, disciplina AMBIGUA…) y ejemplos reales del dataset.
- **`sacks_items.py`**: los 60 enunciados (con variantes por género) y las 15 áreas de la hoja de corrección.
- **`sacks_ejemplos.py`**: memoria de casos y selección de ejemplos few-shot por enunciado.
- **`sacks_llm.py`**: cliente de Ollama (modo rápido con prompt crudo o modo think), parseo tolerante, precalentado y `keep_alive`.
- **`app.py`**: rutas Flask, inicio por roles, autorización de datos, asistente del test en 4 pasos con análisis en
  segundo plano, área del psicólogo, lectura tolerante de CSV, comparación por enunciado y respuesta, y páginas de error amigables.

## Accesibilidad

El botón **Accesibilidad** de la barra superior (atajo Alt + A) abre un panel pensado para baja visión, daltonismo,
dislexia y uso con teclado o lector de pantalla. Las preferencias se recuerdan en el navegador y se aplican antes de
pintar cada página:

- **Tamaño del texto** en cuatro niveles hasta el 200 % (WCAG 1.4.4), respetando el tamaño configurado en el navegador.
- **Colores**: normal, alto contraste (≥ 7:1 y bordes negros), oscuro, invertido y escala de grises.
- **Tipo de letra**: Poppins, Atkinson Hyperlegible Next (diseñada para baja visión), Lexend u OpenDyslexic; todas
  empaquetadas en `static/fonts/` (licencia OFL) para funcionar sin internet.
- **Espaciado de texto** (WCAG 1.4.12), **guía de lectura** que sigue al puntero, **resaltar botones y enlaces**,
  **cursor grande** y **menos animaciones** (también respeta `prefers-reduced-motion`).
- **Leer en voz alta** con voz natural: motor neuronal **Piper** corriendo en este equipo (`sacks_tts.py`, voces
  `es_MX` «Claudia» y `es_ES` «Sara» en `data/voces/`, que `descargar_voces.sh` baja de rhasspy/piper-voices la primera vez) con selector de voz,
  velocidad, «Probar voz» y «Detener». Si Piper no está disponible, usa la voz del sistema prefiriendo Paulina/Mónica
  sobre las voces «de novedad» de macOS (Eddy, Flo…) que suenan robóticas. Con la opción activa se escucha **todo el
  proceso** (`static/lectura.js`): cada pantalla se lee al abrirse (título, qué hacer, paso actual e instrucciones,
  marcadas con `data-leer`), se lee lo que se enfoca con Tab o flechas, el estado de casillas, opciones y listas al
  cambiarlas, los errores y avisos (`role="alert"` y validación del formulario), las ventanas de ayuda y del detalle de
  la autorización, los cambios de pestaña o de página y cualquier texto al que se le hace clic (en las tablas, la fila
  completa con sus encabezados). Los textos largos se leen por oraciones y la siguiente se prepara mientras suena la
  actual. El botón «Escuchar» de la barra (o Alt + L) repite la pantalla o detiene la voz, y Esc la detiene en
  cualquier momento. Ese botón y los de «Escuchar la frase» y «Escuchar resumen» solo aparecen cuando la persona
  activa esta opción, para no recargar la interfaz de quien no la necesita. Como los navegadores no reproducen audio
  antes del primer clic o tecla, la pantalla que abre el lanzador se lee con el primer gesto; las demás, al abrirse.
- Además: enlace «Ir al contenido», foco visible en todos los controles, regiones `aria-live`, roles y nombres
  accesibles, menú de frases navegable con flechas, Esc cierra menús y detiene la voz, y mensajes de validación del
  navegador en español.

## Diseño

Identidad propia y offline: tipografía display **Fraunces** para enunciados y títulos, Poppins para la interfaz,
marca propia (SVG), fotos de Unsplash empaquetadas en `static/img/` (créditos en `CREDITOS.txt`), iconos y tonos por
área del test, badges de categoría con símbolo además de color (+ − ~), barra apilada de distribución y transición
de «pasar página» entre frases.

**Pantalla única:** cada página cabe en la ventana sin desplazarse, de 1024 × 768 a pantallas grandes (verificado
también en 1280 × 720, 1366 × 768, 1440 × 900, 1512 × 860 y 1920 × 1080). Las secciones largas usan pestañas y las
tablas y áreas se paginan según el alto disponible (`static/pantalla.js`). En teléfonos el flujo de la persona también
cabe; las herramientas del psicólogo se desplazan dentro del área central, y con texto ampliado al 150–200 % el contenido
puede desplazarse para no recortar nada (WCAG 1.4.10).

## Requisitos
## Requisitos

- macOS / Linux / Windows con **Python 3.10+**
- **Ollama** instalado y abierto (https://ollama.com/download)
- ~5 GB de disco para el modelo base `deepseek-r1:7b` y ~140 MB para las voces; 8 GB de RAM mínimo (16 GB recomendado)

## Instalación

```bash
# 1. Modelo base y modelo custom
ollama pull deepseek-r1:7b
ollama create deepseek-r1-sacks -f Modelfile

# 2. Entorno de Python
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Ejecución

```bash
source .venv/bin/activate
python app.py
```

Abre http://127.0.0.1:5050 (el navegador se abre solo). En macOS también puedes hacer doble clic en
`iniciar_sacks.command`, que verifica Ollama, crea el modelo si falta y arranca la aplicación.

Variables opcionales: `SACKS_PORT` (puerto, por defecto 5050), `SACKS_MODELO`, `OLLAMA_BASE_URL`,
`SACKS_TIMEOUT` (segundos por frase, 180), `SACKS_MODO` (`rapido` | `think`), `SACKS_FEWSHOT` (ejemplos por
enunciado, 8), `SACKS_CASOS_UMBRAL` (memoria de casos, 0.85; 0 la desactiva), `SACKS_NO_BROWSER=1`.

## Archivos de ejemplo (`static/ejemplos/`)

- `respuestas_demo.csv` – 12 respuestas al test (`Numero, Respuesta`) que cubren varias áreas, incluido el caso «no tengo padre» (≈ 3 min). El botón «Rellenar ejemplo» del test carga estas mismas respuestas.
- `evaluacion_humana_demo.csv` – las mismas 12 respuestas con la categoría asignada por el evaluador humano, para el flujo de comparación.
- `frases_demo.csv` – 8 frases sueltas ya completas (formato `Frase`).

## Estructura del repositorio

```
proyect/
├── app.py                 # Aplicación Flask (3 flujos, jobs en segundo plano, manejo de errores)
├── sacks_llm.py           # Cliente de Ollama (modo rápido / think) + memoria de casos + parseo
├── sacks_items.py         # Los 60 enunciados del SSCT, variantes por género y las 15 áreas
├── sacks_ejemplos.py      # Ejemplos etiquetados por psicólogos: memoria de casos y few-shot
├── data/ejemplos_psicologos.csv  # Dataset del proyecto (52 personas × 60 ítems, etiquetado)
├── Modelfile              # Definición del modelo custom deepseek-r1-sacks
├── iniciar_sacks.command  # Arranque con doble clic en macOS
├── requirements.txt
├── templates/             # base, index, procesar_csv, progreso, resultados, comparar, comparacion, error
├── sacks_tts.py           # Voz neuronal local (Piper) para leer en voz alta
├── evaluar.py             # Evaluación reproducible contra las etiquetas de los psicólogos
├── data/voces/            # Voces Piper es_MX / es_ES (no se versionan; ver descargar_voces.sh)
├── descargar_voces.sh     # Descarga las voces de Piper (~140 MB) la primera vez
├── static/                # style.css, a11y.js, fonts/, img/, favicon, ejemplos/*.csv
├── uploads/               # CSV de prueba históricos
├── processed/             # Resultados generados (ignorado en git)
└── logs/log.csv           # Registro de consultas al modelo (ignorado en git)
```

## Autor

**Yeferson Ferney Culma Montoya** · Ingeniería de Software · Universidad Manuela Beltrán · 2025
