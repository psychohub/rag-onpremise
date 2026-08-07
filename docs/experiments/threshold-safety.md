# Experimento: seguridad del umbral del caché semántico

**Fecha:** agosto 2026
**Autor:** Hubert García Gordon
**Sugerido por:** Giulio D'Erme (comentario en el artículo de dev.to)

---

## Resumen ejecutivo

**En / English (2 sentences):** Empirical test of the semantic cache
threshold using `nomic-embed-text` on Spanish administrative queries.
No safe cosine threshold exists that separates adversarial pairs
(negations, entity swaps, temporal changes) from genuine paraphrases —
adversarial similarities reach 0.9984 while paraphrase similarities stay
below 0.9060. As a consequence, the semantic cache is disabled by default
in this repository.

**Es / Español (2 líneas):** Prueba empírica del umbral del caché semántico
usando `nomic-embed-text` sobre consultas administrativas en español. No
existe umbral coseno seguro que separe pares adversos (negaciones, cambios
de entidad, cambios temporales) de paráfrasis genuinas — las similitudes
adversas llegan a 0.9984 mientras las de paráfrasis se quedan bajo 0.9060.
Como consecuencia, el caché semántico está deshabilitado por defecto en
este repositorio.

---

## 1. Contexto

El `RagService.cs` del repositorio incluye un caché semántico que sirve
respuestas previamente generadas cuando la nueva consulta es
semánticamente similar a una consulta ya cacheada. La medida de similitud
es coseno sobre los embeddings de las dos consultas, con umbral
configurable (0.92 en la implementación original).

En el hilo del artículo publicado en dev.to, Giulio D'Erme cuestionó la
seguridad de ese umbral en dominios donde las respuestas dependen de
distinciones que el modelo de embeddings puede colapsar. Su ejemplo
específico: pares como "pacientes con fiebre" vs "pacientes sin fiebre"
que difieren en un solo token pero tienen respuestas correctas opuestas.
Su hipótesis: en texto clínico o administrativo en español, esos pares
adversos pueden superar el umbral 0.92 mientras las paráfrasis genuinas
se quedan por debajo, y el caché sirve la respuesta equivocada en
silencio.

Este experimento pone la hipótesis a prueba.

## 2. Objetivo

Determinar empíricamente si existe un umbral coseno con
`nomic-embed-text` que satisfaga simultáneamente:

- **Rechazar pares adversos** (negaciones, entidades distintas, tiempos
  distintos) — evitando que el caché sirva respuestas incorrectas.
- **Aceptar paráfrasis genuinas** (misma pregunta reformulada) —
  preservando el beneficio de caché que motivó su inclusión en primer
  lugar.

## 3. Metodología

### 3.1 Modelo evaluado

`nomic-embed-text:latest` corriendo sobre Ollama local.

- Cuantización: F16
- Tamaño: 137M parámetros
- Endpoint: `http://localhost:11434/api/embeddings`

### 3.2 Corpus de prueba

20 pares de consultas construidas manualmente para el experimento (no se
usaron consultas reales de ningún sistema en producción). Dominio:
administración pública en español (RRHH, procedimientos institucionales,
permisos, incapacidades, presupuestos).

Distribución de los pares por categoría:

| Categoría | Pares | Comportamiento esperado del caché |
|---|---|---|
| Negación (con/sin, incluye/excluye) | 5 | Rechazar (respuesta opuesta) |
| Temporal (año, mes, semestre distinto) | 5 | Rechazar (respuesta distinta) |
| Entidad (rol, tipo, categoría distinta) | 5 | Rechazar (respuesta distinta) |
| Paráfrasis (misma pregunta reformulada) | 5 | Aceptar (misma respuesta) |

El listado completo de los 20 pares está en el archivo `pairs.py` de este
directorio.

### 3.3 Procedimiento

1. Para cada par, se calcula el embedding de ambas consultas.
2. Se calcula la similitud coseno entre ambos embeddings.
3. Se agrupan los resultados por categoría.
4. Se analiza si existe un umbral que separe las distribuciones de
   "rechazar" y "aceptar" sin cruzarse.

El script utilizado (`test_threshold.py`) está en este directorio y es
reproducible por cualquier persona con Ollama y `nomic-embed-text`
instalados localmente.

## 4. Resultados

### 4.1 Similitud por categoría

| Categoría | n | mín | máx | media | mediana |
|---|---|---|---|---|---|
| Negación | 5 | 0.9702 | 0.9984 | 0.9837 | 0.9811 |
| Temporal | 5 | 0.9054 | 0.9646 | 0.9372 | 0.9492 |
| Entidad | 5 | 0.7498 | 0.9210 | 0.8641 | 0.8827 |
| Paráfrasis (control) | 5 | 0.7470 | 0.9060 | 0.8067 | 0.7787 |

### 4.2 Comportamiento con el umbral original (0.92)

| Categoría | Pares que superan 0.92 | Diagnóstico |
|---|---|---|
| Negación | 5 / 5 | Falso positivo — caché sirve respuesta contraria |
| Temporal | 3 / 5 | Falso positivo — caché sirve respuesta con fecha equivocada |
| Entidad | 1 / 5 | Falso positivo — caché sirve respuesta de otra entidad |
| Paráfrasis | 0 / 5 | Falso negativo — caché nunca ayuda |

**Total: 9 de 15 pares adversos serían servidos incorrectamente por el
caché. 5 de 5 paráfrasis genuinas serían rechazadas.**

### 4.3 Análisis de umbral seguro

- Similitud más alta entre pares adversos: **0.9984**
- Similitud más baja entre paráfrasis genuinas: **0.7470**

Como la similitud más alta entre pares adversos (0.9984) es
significativamente mayor que la similitud más baja entre paráfrasis
(0.7470), **no existe umbral coseno que satisfaga simultáneamente
"rechazar pares adversos" y "aceptar paráfrasis genuinas"** con esta
combinación de embedder y corpus. Cualquier umbral suficientemente alto
para rechazar los adversos también rechaza todas las paráfrasis.

## 5. Discusión

### 5.1 Por qué las distribuciones se solapan

El modelo `nomic-embed-text` fue entrenado predominantemente sobre texto
en inglés. En español administrativo, la señal semántica que distingue
una negación de su afirmación ("con goce salarial" vs "sin goce salarial")
es un cambio de un solo token, mientras que la señal semántica que
identifica el tema general ("goce salarial", "incapacidad", "documentos
requeridos") ocupa la mayor parte del contenido. El embedder captura el
tema con alta fidelidad y colapsa la distinción crítica.

El mismo fenómeno aplica a cambios temporales (2024 vs 2025) y de
entidad (maternidad vs paternidad, teletrabajo vs trabajo presencial).

Este comportamiento no es exclusivo de `nomic-embed-text`; es una
propiedad conocida de los embeddings basados en transformers entrenados
con contraste semántico general. En dominios donde la respuesta correcta
depende de distinciones finas — clínica, legal, administrativa —
cualquier caché basado únicamente en similitud coseno de embeddings es
un vector de errores silenciosos.

### 5.2 Consecuencia para el diseño del sistema

Un hit del caché nunca llega al LLM. Esto significa que **el caché sirve
respuestas incorrectas con la misma confianza que las correctas**, y no
existe mecanismo en la capa del LLM que pueda detectar el error. El
único momento en que el sistema puede detectar el problema es antes de
servir el hit, y ese momento requiere señales adicionales al coseno
sobre embeddings.

### 5.3 Mitigaciones posibles

Ninguna de estas mitigaciones se implementa en el repositorio hoy, pero
se listan como direcciones futuras razonables:

- **Verificación simbólica antes de servir el hit.** Detección de
  negaciones ("no", "sin", "excluye") o de entidades cambiadas usando
  reglas o NER; si detecta divergencia crítica, invalidar el hit.
- **Embedder especializado en el dominio.** Modelos ajustados sobre
  corpus clínico o administrativo en español pueden distinguir mejor
  negaciones y entidades, aunque no es garantía.
- **Caché por chunks recuperados en lugar de por consulta.** El caché
  guarda el resultado del retrieval (embedding → lista de chunks) en vez
  del resultado de la generación (consulta → respuesta). Ivan Rossouw
  propuso esta variante en el mismo hilo de dev.to. Reduce el ahorro por
  hit pero elimina el vector de error silencioso, porque el LLM sigue
  procesando la nueva consulta contra chunks conocidos.

## 6. Decisión

A la luz de los resultados, el caché semántico se deshabilita por defecto
en este repositorio. La flag `SemanticCacheEnabled` en `RagSettings.cs`
tiene default `false`.

Los usuarios del código pueden habilitar el caché si han verificado que
su combinación específica de embedder + corpus no presenta el problema
demostrado en este experimento. La advertencia correspondiente está en
`RagSettings.cs` y en el `README.md`.

## 7. Reproducibilidad

Este directorio contiene los materiales para reproducir el experimento:

- `pairs.py` — Los 20 pares de consultas utilizados.
- `test_threshold.py` — El script que calcula embeddings, similitudes y
  produce el análisis.

Para ejecutar:

```powershell
# Prerrequisitos: Ollama corriendo localmente con nomic-embed-text descargado.
ollama pull nomic-embed-text

# Correr el experimento:
python test_threshold.py
```

Las cifras exactas pueden variar mínimamente entre ejecuciones debido a
la naturaleza no determinista de algunas operaciones del embedder, pero
la conclusión estructural (solapamiento de distribuciones adversas y de
paráfrasis) es estable en múltiples corridas.

## 8. Referencias

- **Thread original de sugerencia:**
  Giulio D'Erme, comentario en artículo "On-premise RAG without GPU,
  cloud, or Docker" en dev.to. Enlace directo:
  `dev.to/gde03/comment/3c9ni`

- **Thread relacionado sobre partición de caché:**
  Ivan Rossouw, comentario en el mismo artículo. Enlace directo:
  `dev.to/iqtechsolutions/comment/3c9n3`

Ambos comentarios motivaron los cambios en `RagService.cs` de agosto 2026.

---

*Este reporte es material académico personal. No describe deployment
institucional específico ni utiliza datos de ningún sistema en producción.*
