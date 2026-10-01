"""
Los 60 enunciados del Test de Frases Incompletas de Sacks (SSCT) y sus 15 áreas,
tomados del documento «FRASES_INCOMPLETAS.pdf» (Universidad Juárez del Estado de Durango)
que se usó como base en la Práctica Empresarial II.

Los ítems 9, 10, 25, 40, 55 y 57 cambian de redacción según el género de la persona
evaluada (niño/niña, sexo contrario). Solo se usa el género y la edad; no se pide más información.
"""

from __future__ import annotations

# Códigos de género: F = femenino, M = masculino, X = otro / no indicado
GENEROS = {"F": "Femenino", "M": "Masculino", "X": "Otro"}

# Enunciados en el orden original. Un string es fijo; un dict tiene variantes por género.
_ITEMS: dict[int, str | dict[str, str]] = {
    1: "Siento que mi padre raras veces me",
    2: "Cuando tengo mala suerte",
    3: "Siempre anhelé",
    4: "Si yo estuviera a cargo",
    5: "El futuro me parece",
    6: "Las personas que están sobre mí",
    7: "Sé que es tonto, pero tengo miedo de",
    8: "Creo que un verdadero amigo",
    9: {"F": "Cuando era niña", "M": "Cuando era niño", "X": "Cuando era niño(a)"},
    10: {"F": "Mi idea de hombre perfecto", "M": "Mi idea de mujer perfecta", "X": "Mi idea de mujer (hombre) perfecta(o)"},
    11: "Cuando veo a un hombre y a una mujer juntos",
    12: "Comparando las demás familias, la mía",
    13: "En las labores me llevo mejor con",
    14: "Mi madre",
    15: "Haría cualquier cosa por olvidar la vez que",
    16: "Si mi padre tan solo",
    17: "Siento que tengo habilidades para",
    18: "Sería perfectamente feliz si",
    19: "Si la gente trabajara para mí",
    20: "Yo espero",
    21: "En la escuela, mis maestros",
    22: "La mayoría de mis amistades no saben que tengo miedo de",
    23: "No me gusta",
    24: "Antes",
    25: {"F": "Pienso que la mayoría de los muchachos", "M": "Pienso que la mayoría de las muchachas", "X": "Pienso que la mayoría de los muchachos (as)"},
    26: "Yo creo que la vida matrimonial",
    27: "Mi familia me trata como",
    28: "Aquellos con los que trabajo",
    29: "Mi madre y yo",
    30: "Mi más grande error fue",
    31: "Desearía que mi padre",
    32: "Mi mayor debilidad",
    33: "Mi ambición secreta en la vida",
    34: "La gente que trabaja para mí",
    35: "Algún día yo",
    36: "Cuando veo al jefe venir",
    37: "Quisiera perder el miedo de",
    38: "La gente que más me agrada",
    39: "Si fuera joven otra vez",
    40: {"F": "Creo que la mayoría de los hombres", "M": "Creo que la mayoría de las mujeres", "X": "Creo que la mayoría de las mujeres (hombres)"},
    41: "Si tuviera relaciones sexuales",
    42: "La mayoría de las familias que conozco",
    43: "Me gusta trabajar con la gente que",
    44: "Creo que la mayoría de las madres",
    45: "Cuando era más joven me sentía culpable de",
    46: "Siento que mi padre es",
    47: "Cuando la suerte se vuelve en contra mía",
    48: "Cuando doy órdenes, yo",
    49: "Lo que más deseo en la vida es",
    50: "Dentro de algún tiempo",
    51: "La gente a quien yo considero mis superiores",
    52: "Mis temores en ocasiones me obligan a",
    53: "Cuando no estoy, mis amigos",
    54: "Mi más vívido recuerdo de la infancia",
    55: {"F": "Lo que menos me gusta de los hombres", "M": "Lo que menos me gusta de las mujeres", "X": "Lo que menos me gusta de las mujeres (hombres)"},
    56: "Mi vida sexual",
    57: {"F": "Cuando era niña", "M": "Cuando era niño", "X": "Cuando era niño(a)"},
    58: "La gente que trabaja conmigo, generalmente",
    59: "Me agrada mi madre, pero",
    60: "La peor cosa que he hecho",
}

NUMEROS = list(range(1, 61))

# Las 15 áreas de la hoja de corrección SSCT, cada una con sus 4 ítems.
AREAS: list[tuple[str, str, list[int]]] = [
    ("I", "Actitud frente a la madre", [14, 29, 44, 59]),
    ("II", "Actitud frente al padre", [1, 16, 31, 46]),
    ("III", "Actitud frente a la unidad de la familia", [12, 27, 42, 57]),
    ("IV", "Actitud hacia el sexo contrario", [10, 25, 40, 55]),
    ("V", "Actitud hacia las relaciones heterosexuales", [11, 26, 41, 56]),
    ("VI", "Actitud hacia los amigos y conocidos", [8, 23, 38, 53]),
    ("VII", "Actitud frente a los superiores en el trabajo o la escuela", [6, 21, 36, 51]),
    ("VIII", "Actitud hacia las personas supervisadas", [4, 19, 34, 48]),
    ("IX", "Actitud hacia los compañeros en la escuela y el trabajo", [13, 28, 43, 58]),
    ("X", "Temores", [7, 22, 37, 52]),
    ("XI", "Sentimientos de culpa", [15, 30, 45, 60]),
    ("XII", "Actitud hacia las propias habilidades", [2, 17, 32, 47]),
    ("XIII", "Actitud hacia el pasado", [9, 24, 39, 54]),
    ("XIV", "Actitud hacia el futuro", [5, 20, 35, 50]),
    ("XV", "Metas", [3, 18, 33, 49]),
]

AREA_DE_ITEM: dict[int, tuple[str, str]] = {
    n: (romano, nombre) for romano, nombre, numeros in AREAS for n in numeros
}


def codigo_genero(genero) -> str:
    """'Femenino' -> F, 'Masculino' -> M, cualquier otra cosa -> X."""
    texto = (str(genero or "")).strip().lower()
    if texto.startswith(("f", "muj")):
        return "F"
    if texto.startswith(("m", "h", "var")):
        return "M"
    return "X"


def enunciado(numero: int, genero="") -> str:
    """Enunciado del ítem, adaptado al género cuando aplica."""
    item = _ITEMS[int(numero)]
    if isinstance(item, dict):
        return item[codigo_genero(genero)]
    return item


def variantes(numero: int) -> dict[str, str]:
    """Las tres variantes (F/M/X) del enunciado; iguales si el ítem no cambia."""
    item = _ITEMS[int(numero)]
    if isinstance(item, dict):
        return dict(item)
    return {"F": item, "M": item, "X": item}


def frase_completa(numero: int, respuesta: str, genero="") -> str:
    """Une el enunciado con la respuesta de la persona: 'Mi madre' + 'es mi apoyo' -> 'Mi madre es mi apoyo'."""
    inicio = enunciado(numero, genero)
    fin = (respuesta or "").strip()
    if not fin:
        return inicio
    if fin[0] in ".,;:!?…":
        return inicio + fin
    return f"{inicio} {fin}"


def area_de(numero) -> tuple[str, str] | None:
    try:
        return AREA_DE_ITEM.get(int(numero))
    except (TypeError, ValueError):
        return None
