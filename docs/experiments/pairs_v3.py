"""
Pares de preguntas para el experimento de umbral (v3).

Cambios respecto de pairs_v2.py
-------------------------------
1. RECLASIFICACION. Los pares neg-04 y neg-05 de v2 estaban mal
   etiquetados. En español, la interrogativa negativa confirmatoria
   ("¿No es obligatorio X?") NO invierte la respuesta correcta: un
   sistema correcto responde lo mismo que a "¿Es obligatorio X?".
   Esos pares pasan a la categoria "confirmatory" con expected_behavior
   "accept", y con IDs nuevos (cnf-01, cnf-02) para no reciclar
   identificadores entre versiones del experimento.

2. NEGACIONES AMPLIADAS. La categoria "negation" pasa de n=5 (de los
   cuales 2 eran invalidos) a n=9 limpios. Se conservan neg-01 a
   neg-03 con sus IDs y textos originales; los nuevos empiezan en
   neg-06. Los IDs neg-04 y neg-05 quedan retirados a proposito.

3. CONTROL DE SOLAPAMIENTO LEXICO. Las 5 parafrasis originales
   comparten pocos tokens entre query y twin, mientras que los pares
   de negacion comparten casi todos. Esa asimetria es un confound: no
   permite distinguir "el embedder colapsa la negacion" de "el
   embedder sigue la forma superficial". Se agregan 5 parafrasis de
   ALTO solapamiento (cambio de un solo token, sinonimo) que igualan
   la distancia lexica de las negaciones con comportamiento esperado
   opuesto. Las originales quedan como "paraphrase-low".

4. CAMPO "mechanism" en las negaciones, para poder reportar si el
   colapso depende del tipo de inversion de polaridad.

5. ESCOPO INGLES AUTOSUFICIENTE. PAIRS_EN ahora incluye categorias
   accept, de modo que el analisis de umbral seguro aplica tambien
   ahi (en v2 el scope EN solo tenia negaciones y el analisis no
   corria).

Categorias
----------
  negation         reject   inversion de polaridad, respuesta opuesta
  temporal         reject   cambio de año, mes o periodo
  entity           reject   cambio de rol, tipo o categoria
  confirmatory     accept   interrogativa negativa, misma respuesta
  paraphrase-low   accept   reformulacion, bajo solapamiento lexico
  paraphrase-high  accept   reformulacion, alto solapamiento lexico

Dominio: administracion publica / RRHH / procedimientos
institucionales. No se usan consultas reales de ningun sistema en
produccion.

Ver docs/experiments/threshold-safety.md para el contexto.
"""

PAIRS_ES = [
    # =========================================================
    # NEGACION (n=9) - el twin NO debe pasar el umbral.
    # La respuesta correcta es distinta u opuesta.
    # =========================================================
    {
        "id": "neg-01",
        "category": "negation",
        "mechanism": "with_without",
        "language": "es",
        "expected_behavior": "reject",
        "query": "¿Los funcionarios con dedicación exclusiva pueden dar clases en universidades?",
        "twin":  "¿Los funcionarios sin dedicación exclusiva pueden dar clases en universidades?",
    },
    {
        "id": "neg-02",
        "category": "negation",
        "mechanism": "with_without",
        "language": "es",
        "expected_behavior": "reject",
        "query": "¿Qué documentos se requieren para tramitar una incapacidad con goce salarial?",
        "twin":  "¿Qué documentos se requieren para tramitar una incapacidad sin goce salarial?",
    },
    {
        "id": "neg-03",
        "category": "negation",
        "mechanism": "include_exclude",
        "language": "es",
        "expected_behavior": "reject",
        "query": "¿El permiso de estudios incluye el pago de matrícula?",
        "twin":  "¿El permiso de estudios excluye el pago de matrícula?",
    },

    # neg-04 y neg-05 retirados en v3 -> ver cnf-01 y cnf-02.

    {
        "id": "neg-06",
        "category": "negation",
        "mechanism": "with_without",
        "language": "es",
        "expected_behavior": "reject",
        "query": "¿Qué beneficios tienen los funcionarios con nombramiento en propiedad?",
        "twin":  "¿Qué beneficios tienen los funcionarios sin nombramiento en propiedad?",
    },
    {
        "id": "neg-07",
        "category": "negation",
        "mechanism": "with_without",
        "language": "es",
        "expected_behavior": "reject",
        "query": "¿Qué trámites puede realizar un usuario con firma digital registrada?",
        "twin":  "¿Qué trámites puede realizar un usuario sin firma digital registrada?",
    },
    {
        "id": "neg-08",
        "category": "negation",
        "mechanism": "with_without",
        "language": "es",
        "expected_behavior": "reject",
        "query": "¿Los estudiantes con beca deben pagar el certificado de notas?",
        "twin":  "¿Los estudiantes sin beca deben pagar el certificado de notas?",
    },
    {
        "id": "neg-09",
        "category": "negation",
        "mechanism": "include_exclude",
        "language": "es",
        "expected_behavior": "reject",
        "query": "¿El reporte mensual incluye los datos de establecimientos privados?",
        "twin":  "¿El reporte mensual excluye los datos de establecimientos privados?",
    },
    {
        "id": "neg-10",
        "category": "negation",
        "mechanism": "permit_prohibit",
        "language": "es",
        "expected_behavior": "reject",
        "query": "¿El reglamento permite acumular vacaciones de un año a otro?",
        "twin":  "¿El reglamento prohíbe acumular vacaciones de un año a otro?",
    },
    {
        "id": "neg-11",
        "category": "negation",
        "mechanism": "permit_prohibit",
        "language": "es",
        "expected_behavior": "reject",
        "query": "¿Está autorizado el uso de dispositivos personales en la red institucional?",
        "twin":  "¿Está prohibido el uso de dispositivos personales en la red institucional?",
    },

    # =========================================================
    # CONFIRMATORY (n=2) - el twin SI debe pasar.
    # Interrogativa negativa confirmatoria: misma respuesta.
    # Eran neg-04 y neg-05 en pairs_v2.py.
    # =========================================================
    {
        "id": "cnf-01",
        "category": "confirmatory",
        "language": "es",
        "expected_behavior": "accept",
        "was_in_v2_as": "neg-04",
        "query": "¿Es obligatorio presentar la solicitud con anticipación?",
        "twin":  "¿No es obligatorio presentar la solicitud con anticipación?",
    },
    {
        "id": "cnf-02",
        "category": "confirmatory",
        "language": "es",
        "expected_behavior": "accept",
        "was_in_v2_as": "neg-05",
        "query": "¿Los contratos temporales tienen derecho a aguinaldo?",
        "twin":  "¿Los contratos temporales no tienen derecho a aguinaldo?",
    },

    # =========================================================
    # TEMPORAL (n=5) - sin cambios respecto de v2.
    # =========================================================
    {
        "id": "tmp-01", "category": "temporal", "language": "es", "expected_behavior": "reject",
        "query": "¿Cuál fue el presupuesto asignado a la institución en 2024?",
        "twin":  "¿Cuál fue el presupuesto asignado a la institución en 2025?",
    },
    {
        "id": "tmp-02", "category": "temporal", "language": "es", "expected_behavior": "reject",
        "query": "¿Qué reformas se aprobaron en enero?",
        "twin":  "¿Qué reformas se aprobaron en marzo?",
    },
    {
        "id": "tmp-03", "category": "temporal", "language": "es", "expected_behavior": "reject",
        "query": "¿Cuántas plazas se ocuparon durante el primer semestre?",
        "twin":  "¿Cuántas plazas se ocuparon durante el segundo semestre?",
    },
    {
        "id": "tmp-04", "category": "temporal", "language": "es", "expected_behavior": "reject",
        "query": "¿Cuál es el calendario de vacaciones colectivas para diciembre?",
        "twin":  "¿Cuál es el calendario de vacaciones colectivas para julio?",
    },
    {
        "id": "tmp-05", "category": "temporal", "language": "es", "expected_behavior": "reject",
        "query": "¿Qué modificaciones entraron en vigencia en 2023?",
        "twin":  "¿Qué modificaciones entraron en vigencia en 2026?",
    },

    # =========================================================
    # ENTIDAD (n=5) - sin cambios respecto de v2.
    # =========================================================
    {
        "id": "ent-01", "category": "entity", "language": "es", "expected_behavior": "reject",
        "query": "¿Cuáles son las funciones del jefe de departamento?",
        "twin":  "¿Cuáles son las funciones del jefe de área?",
    },
    {
        "id": "ent-02", "category": "entity", "language": "es", "expected_behavior": "reject",
        "query": "¿Qué requisitos aplican para las plazas profesionales?",
        "twin":  "¿Qué requisitos aplican para las plazas técnicas?",
    },
    {
        "id": "ent-03", "category": "entity", "language": "es", "expected_behavior": "reject",
        "query": "¿Cómo se solicita una licencia por maternidad?",
        "twin":  "¿Cómo se solicita una licencia por paternidad?",
    },
    {
        "id": "ent-04", "category": "entity", "language": "es", "expected_behavior": "reject",
        "query": "¿Qué establece el reglamento sobre teletrabajo?",
        "twin":  "¿Qué establece el reglamento sobre trabajo presencial?",
    },
    {
        "id": "ent-05", "category": "entity", "language": "es", "expected_behavior": "reject",
        "query": "¿Cuál es el procedimiento para solicitar un traslado interno?",
        "twin":  "¿Cuál es el procedimiento para solicitar un ascenso interno?",
    },

    # =========================================================
    # PARAFRASIS BAJO SOLAPAMIENTO (n=5) - el twin SI debe pasar.
    # Eran "paraphrase" en v2, mismos IDs y textos.
    # =========================================================
    {
        "id": "par-01", "category": "paraphrase-low", "language": "es", "expected_behavior": "accept",
        "query": "¿Cómo solicito vacaciones?",
        "twin":  "¿Cuál es el procedimiento para pedir vacaciones?",
    },
    {
        "id": "par-02", "category": "paraphrase-low", "language": "es", "expected_behavior": "accept",
        "query": "¿Qué documentos necesito para inscribir un permiso?",
        "twin":  "¿Cuáles son los documentos requeridos para tramitar un permiso?",
    },
    {
        "id": "par-03", "category": "paraphrase-low", "language": "es", "expected_behavior": "accept",
        "query": "¿Cuántos días de vacaciones me corresponden por año?",
        "twin":  "¿Cuál es la cantidad de días de vacaciones anuales que tengo derecho?",
    },
    {
        "id": "par-04", "category": "paraphrase-low", "language": "es", "expected_behavior": "accept",
        "query": "¿Dónde presento la solicitud de incapacidad?",
        "twin":  "¿En qué oficina se entrega la solicitud de incapacidad?",
    },
    {
        "id": "par-05", "category": "paraphrase-low", "language": "es", "expected_behavior": "accept",
        "query": "¿Qué pasa si no presento el formulario a tiempo?",
        "twin":  "¿Cuáles son las consecuencias de no entregar el formulario en el plazo establecido?",
    },

    # =========================================================
    # PARAFRASIS ALTO SOLAPAMIENTO (n=5) - el twin SI debe pasar.
    # Cambio de un solo token (sinonimo). Igualan la distancia
    # lexica de los pares de negacion, con comportamiento
    # esperado OPUESTO. Este es el control que separa
    # "colapso semantico" de "seguir la forma superficial".
    # =========================================================
    {
        "id": "parhi-01", "category": "paraphrase-high", "language": "es", "expected_behavior": "accept",
        "query": "¿Cómo solicito vacaciones ante mi jefatura?",
        "twin":  "¿Cómo pido vacaciones ante mi jefatura?",
    },
    {
        "id": "parhi-02", "category": "paraphrase-high", "language": "es", "expected_behavior": "accept",
        "query": "¿Qué documentos necesito para tramitar un permiso de estudios?",
        "twin":  "¿Qué documentos requiero para tramitar un permiso de estudios?",
    },
    {
        "id": "parhi-03", "category": "paraphrase-high", "language": "es", "expected_behavior": "accept",
        "query": "¿Cuántos días de vacaciones me corresponden por año?",
        "twin":  "¿Cuántos días de vacaciones me tocan por año?",
    },
    {
        "id": "parhi-04", "category": "paraphrase-high", "language": "es", "expected_behavior": "accept",
        "query": "¿Dónde presento la solicitud de incapacidad?",
        "twin":  "¿Dónde entrego la solicitud de incapacidad?",
    },
    {
        "id": "parhi-05", "category": "paraphrase-high", "language": "es", "expected_behavior": "accept",
        "query": "¿Cuál es el plazo para apelar una resolución administrativa?",
        "twin":  "¿Cuál es el plazo para recurrir una resolución administrativa?",
    },
]


# =============================================================
# INGLES - espejo del set español, autosuficiente.
# Incluye negaciones (reject), confirmatorias (accept) y
# parafrasis de alto solapamiento (accept), de modo que el
# analisis de umbral seguro aplique tambien en este scope.
# =============================================================
PAIRS_EN = [
    # --- NEGACION (n=9) ---
    {
        "id": "neg-01-en", "category": "negation", "mechanism": "with_without",
        "language": "en", "expected_behavior": "reject",
        "query": "Can civil servants with exclusive dedication teach at universities?",
        "twin":  "Can civil servants without exclusive dedication teach at universities?",
    },
    {
        "id": "neg-02-en", "category": "negation", "mechanism": "with_without",
        "language": "en", "expected_behavior": "reject",
        "query": "What documents are required to process paid sick leave?",
        "twin":  "What documents are required to process unpaid sick leave?",
    },
    {
        "id": "neg-03-en", "category": "negation", "mechanism": "include_exclude",
        "language": "en", "expected_behavior": "reject",
        "query": "Does the study permit include tuition payment?",
        "twin":  "Does the study permit exclude tuition payment?",
    },
    {
        "id": "neg-06-en", "category": "negation", "mechanism": "with_without",
        "language": "en", "expected_behavior": "reject",
        "query": "What benefits do employees with permanent appointment receive?",
        "twin":  "What benefits do employees without permanent appointment receive?",
    },
    {
        "id": "neg-07-en", "category": "negation", "mechanism": "with_without",
        "language": "en", "expected_behavior": "reject",
        "query": "What procedures can a user with a registered digital signature complete?",
        "twin":  "What procedures can a user without a registered digital signature complete?",
    },
    {
        "id": "neg-08-en", "category": "negation", "mechanism": "with_without",
        "language": "en", "expected_behavior": "reject",
        "query": "Do students with a scholarship have to pay for the transcript?",
        "twin":  "Do students without a scholarship have to pay for the transcript?",
    },
    {
        "id": "neg-09-en", "category": "negation", "mechanism": "include_exclude",
        "language": "en", "expected_behavior": "reject",
        "query": "Does the monthly report include data from private facilities?",
        "twin":  "Does the monthly report exclude data from private facilities?",
    },
    {
        "id": "neg-10-en", "category": "negation", "mechanism": "permit_prohibit",
        "language": "en", "expected_behavior": "reject",
        "query": "Do the regulations allow carrying over vacation days to the next year?",
        "twin":  "Do the regulations forbid carrying over vacation days to the next year?",
    },
    {
        "id": "neg-11-en", "category": "negation", "mechanism": "permit_prohibit",
        "language": "en", "expected_behavior": "reject",
        "query": "Is the use of personal devices on the institutional network authorized?",
        "twin":  "Is the use of personal devices on the institutional network prohibited?",
    },

    # --- CONFIRMATORY (n=2) ---
    {
        "id": "cnf-01-en", "category": "confirmatory", "language": "en",
        "expected_behavior": "accept", "was_in_v2_as": "neg-04-en",
        "query": "Is it mandatory to submit the request in advance?",
        "twin":  "Is it not mandatory to submit the request in advance?",
    },
    {
        "id": "cnf-02-en", "category": "confirmatory", "language": "en",
        "expected_behavior": "accept", "was_in_v2_as": "neg-05-en",
        "query": "Are temporary contracts entitled to a Christmas bonus?",
        "twin":  "Are temporary contracts not entitled to a Christmas bonus?",
    },

    # --- PARAFRASIS ALTO SOLAPAMIENTO (n=5) ---
    {
        "id": "parhi-01-en", "category": "paraphrase-high", "language": "en",
        "expected_behavior": "accept",
        "query": "How do I request vacation days from my supervisor?",
        "twin":  "How do I ask for vacation days from my supervisor?",
    },
    {
        "id": "parhi-02-en", "category": "paraphrase-high", "language": "en",
        "expected_behavior": "accept",
        "query": "What documents do I need to process a study permit?",
        "twin":  "What documents do I require to process a study permit?",
    },
    {
        "id": "parhi-03-en", "category": "paraphrase-high", "language": "en",
        "expected_behavior": "accept",
        "query": "How many vacation days am I entitled to per year?",
        "twin":  "How many vacation days do I get per year?",
    },
    {
        "id": "parhi-04-en", "category": "paraphrase-high", "language": "en",
        "expected_behavior": "accept",
        "query": "Where do I submit the sick leave request?",
        "twin":  "Where do I hand in the sick leave request?",
    },
    {
        "id": "parhi-05-en", "category": "paraphrase-high", "language": "en",
        "expected_behavior": "accept",
        "query": "What is the deadline to appeal an administrative decision?",
        "twin":  "What is the deadline to challenge an administrative decision?",
    },
]


# Todos juntos, para iteracion uniforme
PAIRS_ALL = PAIRS_ES + PAIRS_EN

# Orden canonico de categorias, para reportes
CATEGORIES = [
    "negation",
    "temporal",
    "entity",
    "confirmatory",
    "paraphrase-low",
    "paraphrase-high",
]

# Mapeo de IDs retirados entre versiones, para trazabilidad
RETIRED_IDS = {
    "neg-04": "cnf-01",
    "neg-05": "cnf-02",
    "neg-04-en": "cnf-01-en",
    "neg-05-en": "cnf-02-en",
}
