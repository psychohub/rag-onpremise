"""
Pares de preguntas para probar el umbral de similitud del caché semántico.

Cada par está compuesto por:
  - query: la consulta original
  - twin: la variante crítica
  - category: tipo de par (negation | temporal | entity | paraphrase)
  - expected_behavior:
      "reject" — el twin NO debe pasar el umbral (respuesta distinta)
      "accept" — el twin SÍ debe pasar el umbral (misma respuesta)

Dominio: administración pública / RRHH / procedimientos institucionales.
No se usan queries reales de ningún sistema en producción.
"""

PAIRS = [
    # ─────────────────────────────────────────────────────────
    # NEGACIÓN — el twin no debe pasar (respuestas opuestas)
    # ─────────────────────────────────────────────────────────
    {
        "id": "neg-01",
        "category": "negation",
        "expected_behavior": "reject",
        "query": "¿Los funcionarios con dedicación exclusiva pueden dar clases en universidades?",
        "twin":  "¿Los funcionarios sin dedicación exclusiva pueden dar clases en universidades?",
    },
    {
        "id": "neg-02",
        "category": "negation",
        "expected_behavior": "reject",
        "query": "¿Qué documentos se requieren para tramitar una incapacidad con goce salarial?",
        "twin":  "¿Qué documentos se requieren para tramitar una incapacidad sin goce salarial?",
    },
    {
        "id": "neg-03",
        "category": "negation",
        "expected_behavior": "reject",
        "query": "¿El permiso de estudios incluye el pago de matrícula?",
        "twin":  "¿El permiso de estudios excluye el pago de matrícula?",
    },
    {
        "id": "neg-04",
        "category": "negation",
        "expected_behavior": "reject",
        "query": "¿Es obligatorio presentar la solicitud con anticipación?",
        "twin":  "¿No es obligatorio presentar la solicitud con anticipación?",
    },
    {
        "id": "neg-05",
        "category": "negation",
        "expected_behavior": "reject",
        "query": "¿Los contratos temporales tienen derecho a aguinaldo?",
        "twin":  "¿Los contratos temporales no tienen derecho a aguinaldo?",
    },

    # ─────────────────────────────────────────────────────────
    # TEMPORAL — el twin no debe pasar (año/mes distintos)
    # ─────────────────────────────────────────────────────────
    {
        "id": "tmp-01",
        "category": "temporal",
        "expected_behavior": "reject",
        "query": "¿Cuál fue el presupuesto asignado a la institución en 2024?",
        "twin":  "¿Cuál fue el presupuesto asignado a la institución en 2025?",
    },
    {
        "id": "tmp-02",
        "category": "temporal",
        "expected_behavior": "reject",
        "query": "¿Qué reformas se aprobaron en enero?",
        "twin":  "¿Qué reformas se aprobaron en marzo?",
    },
    {
        "id": "tmp-03",
        "category": "temporal",
        "expected_behavior": "reject",
        "query": "¿Cuántas plazas se ocuparon durante el primer semestre?",
        "twin":  "¿Cuántas plazas se ocuparon durante el segundo semestre?",
    },
    {
        "id": "tmp-04",
        "category": "temporal",
        "expected_behavior": "reject",
        "query": "¿Cuál es el calendario de vacaciones colectivas para diciembre?",
        "twin":  "¿Cuál es el calendario de vacaciones colectivas para julio?",
    },
    {
        "id": "tmp-05",
        "category": "temporal",
        "expected_behavior": "reject",
        "query": "¿Qué modificaciones entraron en vigencia en 2023?",
        "twin":  "¿Qué modificaciones entraron en vigencia en 2026?",
    },

    # ─────────────────────────────────────────────────────────
    # ENTIDAD — el twin no debe pasar (nombres/roles distintos)
    # ─────────────────────────────────────────────────────────
    {
        "id": "ent-01",
        "category": "entity",
        "expected_behavior": "reject",
        "query": "¿Cuáles son las funciones del jefe de departamento?",
        "twin":  "¿Cuáles son las funciones del jefe de área?",
    },
    {
        "id": "ent-02",
        "category": "entity",
        "expected_behavior": "reject",
        "query": "¿Qué requisitos aplican para las plazas profesionales?",
        "twin":  "¿Qué requisitos aplican para las plazas técnicas?",
    },
    {
        "id": "ent-03",
        "category": "entity",
        "expected_behavior": "reject",
        "query": "¿Cómo se solicita una licencia por maternidad?",
        "twin":  "¿Cómo se solicita una licencia por paternidad?",
    },
    {
        "id": "ent-04",
        "category": "entity",
        "expected_behavior": "reject",
        "query": "¿Qué establece el reglamento sobre teletrabajo?",
        "twin":  "¿Qué establece el reglamento sobre trabajo presencial?",
    },
    {
        "id": "ent-05",
        "category": "entity",
        "expected_behavior": "reject",
        "query": "¿Cuál es el procedimiento para solicitar un traslado interno?",
        "twin":  "¿Cuál es el procedimiento para solicitar un ascenso interno?",
    },

    # ─────────────────────────────────────────────────────────
    # PARÁFRASIS — el twin SÍ debe pasar (misma respuesta)
    # ─────────────────────────────────────────────────────────
    {
        "id": "par-01",
        "category": "paraphrase",
        "expected_behavior": "accept",
        "query": "¿Cómo solicito vacaciones?",
        "twin":  "¿Cuál es el procedimiento para pedir vacaciones?",
    },
    {
        "id": "par-02",
        "category": "paraphrase",
        "expected_behavior": "accept",
        "query": "¿Qué documentos necesito para inscribir un permiso?",
        "twin":  "¿Cuáles son los documentos requeridos para tramitar un permiso?",
    },
    {
        "id": "par-03",
        "category": "paraphrase",
        "expected_behavior": "accept",
        "query": "¿Cuántos días de vacaciones me corresponden por año?",
        "twin":  "¿Cuál es la cantidad de días de vacaciones anuales que tengo derecho?",
    },
    {
        "id": "par-04",
        "category": "paraphrase",
        "expected_behavior": "accept",
        "query": "¿Dónde presento la solicitud de incapacidad?",
        "twin":  "¿En qué oficina se entrega la solicitud de incapacidad?",
    },
    {
        "id": "par-05",
        "category": "paraphrase",
        "expected_behavior": "accept",
        "query": "¿Qué pasa si no presento el formulario a tiempo?",
        "twin":  "¿Cuáles son las consecuencias de no entregar el formulario en el plazo establecido?",
    },
]
