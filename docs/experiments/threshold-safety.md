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

> **Errata (agosto 2026).** El techo de 0.9060 vale únicamente para las
> paráfrasis de bajo solapamiento léxico usadas en la primera corrida.
> Con paráfrasis de alto solapamiento y el mismo embedder, el máximo es
> 0.9745. La conclusión —que no existe umbral seguro— se sostiene, pero
> por un margen menor que el que sugiere esta cifra. Ver §9.0 y §9.5.

---

## 1. Contexto

El `RagService.cs` del repositorio incluye un caché semántico que sirve
respuestas previamente generadas cuando la nueva consulta es
semánticamente similar a una consulta ya cacheada. La medida de similitud
es coseno sobre los embeddings de las dos consultas, con umbral
configurable (0.92 en la implementación original).

> **Errata (agosto 2026).** El umbral no es configurable, y no lo era
> cuando se escribió esta línea. Es `SIMILARITY_THRESHOLD`, una
> `private const float` de `RagService.cs`, y `RagSettings` no expone
> ninguna propiedad equivalente: no hay clave que poner en
> `appsettings.json`. Cambiarlo requiere editar el código y recompilar.
> La cifra 0.92 sí es correcta.

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

> **Errata (agosto 2026):** dos de los cinco pares de negación estaban
> mal clasificados; el conteo correcto es 7 de 13. Ver §9.0.

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

> **Errata (agosto 2026).** Esta subsección tiene dos afirmaciones que no
> se sostienen. La atribución al español está refutada por medición
> propia: los mismos pares de negación traducidos al inglés colapsan
> igual. Y la generalización a "los embeddings basados en transformers"
> no tenía fuente, además de que la medición posterior la matiza — otro
> embedder sí resuelve entidad y tiempo. Ver §9.2 y §9.3.

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

> **Errata (agosto 2026).** No se observó tal variación. Comparando 78
> pares entre dos corridas independientes, las similitudes coinciden a
> cuatro decimales sin excepción. Se retira la advertencia sobre no
> determinismo; la afirmación sobre estabilidad de la conclusión sí se
> confirma. Ver §9.5.

## 8. Referencias

- **Thread original de sugerencia:**
  Giulio D'Erme, comentario en artículo "On-premise RAG without GPU,
  cloud, or Docker" en dev.to. Enlace directo:
  `dev.to/gde03/comment/3c9ni`

- **Thread relacionado sobre partición de caché:**
  Ivan Rossouw, comentario en el mismo artículo. Enlace directo:
  `dev.to/iqtechsolutions/comment/3c9n3`

Ambos comentarios motivaron los cambios en `RagService.cs` de agosto 2026.

## 9. Errata y ampliación (agosto 2026)

Este reporte documentó la primera corrida del experimento: 20 pares, un
embedder, español. Corridas posteriores ampliaron el corpus a 31 pares en
español y 16 en inglés, agregaron un segundo embedder y dos
cross-encoders, y cambiaron la forma de reportar. Esta sección corrige lo
que quedó mal y registra lo que se aprendió después.

**Las secciones 1 a 8 se conservan sin modificar**, como registro de lo
que se publicó. Eso no significa que todas sus cifras sigan siendo
correctas: §9.0 y §9.5 listan cuáles no lo son. El documento está
enlazado públicamente, y reescribirlas en su lugar sería peor que
corregirlas acá.

**La conclusión operativa no cambia.** El caché semántico sigue
deshabilitado por defecto, y la evidencia posterior la refuerza: bajo
barrido completo de umbrales con `nomic-embed-text` en español, el umbral
más bajo que produce cero falsos positivos es 1.000, y ahí sobreviven 0
de 12 hits legítimos. La configuración que minimiza errores es no
cachear.

Esta errata corrige dos errores del experimento original. Uno es de
clasificación: dos pares de la categoría "Negación" no eran negaciones en
el sentido que el experimento requiere (§9.0). El otro es de diseño, y es
el más importante: **el control estaba mal elegido** (§9.1).

La sección 4 concluyó que no existe umbral seguro comparando pares
adversos —que difieren de su gemela en un solo token— contra paráfrasis
que compartían pocos tokens con la suya. Las dos poblaciones no eran
comparables en forma superficial. Parte de la separación observada podía
explicarse por solapamiento léxico en vez de por semántica, y eso
significa que la conclusión podía ser correcta y el argumento igual ser
inválido.

Al repetir el experimento con paráfrasis de solapamiento igualado, la
conclusión se sostuvo (§9.1). El caché sigue deshabilitado y por la misma
razón de fondo. Lo que cambió es la calidad del argumento: el margen real
es menor que el publicado, y la evidencia que el reporte original citó
como resultado principal resultó ser la más débil de las disponibles.

El colapso de la negación en embeddings de propósito general no es un
hallazgo nuevo. Que un control mal elegido pueda sostener una conclusión
correcta por el motivo equivocado sí es específico de este experimento, y
es la razón por la que esta errata lo trata como su resultado principal.

### 9.0 Dos pares estaban mal clasificados

Dos de los cinco pares de la categoría "Negación" de §4.1 no eran
negaciones en el sentido que el experimento requiere:

- `neg-04`: "¿Es obligatorio presentar la solicitud con anticipación?"
  contra "¿No es obligatorio presentar la solicitud con anticipación?"
- `neg-05`: "¿Los contratos temporales tienen derecho a aguinaldo?"
  contra "¿Los contratos temporales no tienen derecho a aguinaldo?"

En español la interrogativa negativa es confirmatoria: pide confirmar
lo mismo que la afirmativa. Un sistema correcto responde igual a
ambas. Estaban clasificados como pares que el caché debe **rechazar**
cuando en realidad debe **aceptarlos**.

Consecuencias sobre las cifras publicadas:

- **§4.1, fila Negación.** El mínimo de 0.9702 corresponde a `neg-05`,
  un par inválido. La fila describe cinco pares de los cuales tres
  eran válidos.
- **§4.2.** "9 de 15 pares adversos" pasa a 7 de 13.
- **§4.3 no cambia.** La similitud adversa máxima, 0.9984, es
  `neg-02`, un par válido. La conclusión y la decisión de §6 se
  sostienen sin apoyarse en los pares retirados.

En el corpus ampliado ambos pares sobreviven como `cnf-01` y `cnf-02`,
en la categoría `confirmatory`, con comportamiento esperado "aceptar".
Los identificadores `neg-04` y `neg-05` quedaron retirados y no se
reutilizaron: las negaciones nuevas empiezan en `neg-06`, para que
nadie compare ambas versiones y encuentre que el mismo identificador
designa dos pares distintos. El campo `was_in_v2_as` preserva la traza.

El error se detectó al construir el corpus ampliado, no al ser
señalado externamente.

### 9.1 El control era demasiado fácil

La categoría "Paráfrasis (control)" de §4.1 está compuesta enteramente
por paráfrasis de **bajo solapamiento léxico**: la consulta y su gemela
comparten pocos tokens. Los pares adversos, en cambio, difieren en un
solo token. Comparar unos contra otros produce separación aparente que
puede explicarse por forma superficial y no por semántica.

El corpus ampliado agregó paráfrasis de **alto** solapamiento — que
difieren en un token, igual que los adversos. Con el solapamiento
controlado la conclusión se sostiene, pero el margen es el que hay que
citar:

| Contraste (`nomic-embed-text`, español) | AUC | margen | p exacto |
|---|---|---|---|
| paráfrasis alta vs negación (solapamiento igualado) | 0.1333 | −0.1017 | 0.0290 |
| paráfrasis baja vs negación (solapamiento NO igualado) | 0.0000 | −0.2514 | 0.0010 |

La segunda fila es la que sostenía el reporte original. Es la más vistosa
y la más confundida. **La primera es la válida.**

Que la distinción importa se demuestra con el otro embedder: `bge-m3` da
AUC 0.3556 en el contraste no igualado y 0.9333 en el igualado, sobre los
mismos pares adversos. La única diferencia entre ambos es el solapamiento
léxico de la población de control.

### 9.2 No es el español

§5.1 atribuyó el colapso a que `nomic-embed-text` se entrenó
mayoritariamente sobre inglés y a que en español administrativo la
negación es un cambio de un solo token. **Esa explicación no se
sostiene.** Los nueve pares de negación se tradujeron al inglés y se
volvieron a medir con el mismo modelo: colapsan igual (AUC 0.4444,
p=0.7972, margen −0.0707). El fenómeno es del modelo, no del idioma.

La parte de la explicación que sí se sostiene es la otra: la señal que
identifica el tema ocupa la mayor parte del contenido y el embedder la
captura con alta fidelidad, mientras que la señal de polaridad es mínima.
Eso es independiente del idioma.

Se retira además la afirmación de que este comportamiento es "una
propiedad conocida de los embeddings basados en transformers". No tenía
fuente, y la medición de §9.3 la matiza.

### 9.3 Otro embedder resuelve parte del problema, no la polaridad

`bge-m3` sobre los mismos pares en español:

| Contraste | AUC | margen |
|---|---|---|
| paráfrasis alta vs temporal | 1.0000 | +0.0484 |
| paráfrasis alta vs entidad | 1.0000 | +0.0669 |
| paráfrasis alta vs negación | 0.9333 | **−0.0086** |

Resuelve limpiamente entidad y tiempo, que `nomic-embed-text` no
resolvía. En polaridad queda **indeterminado**: el margen es negativo, y
su signo lo decide un solo par — quitando `parhi-05` pasa a +0.0209. Con
n=14 los datos no alcanzan para decidir de qué lado está. La afirmación
correcta no es "bge-m3 funciona", es "no lo sabemos".

### 9.4 Un cross-encoder no lo arregla

Se probó `cross-encoder/ms-marco-MiniLM-L-6-v2` como paso de confirmación
sobre los mismos pares, puntuando en ambas direcciones — un cross-encoder
es asimétrico y un caché necesita una relación simétrica. Resultado
negativo: en español el contraste primario no alcanza significancia
(AUC 0.3333, p=0.3636) y en inglés el puntaje está
**significativamente invertido** (AUC 0.0667, p=0.0070, margen −6.27 en
unidades de logit). En ambos idiomas el punto de operación que minimiza
errores vuelve a ser no cachear.

La razón es estructural y se lee en las distribuciones: en inglés, las
dos poblaciones que hay que **aceptar** quedan una por debajo y otra por
encima de la población que hay que **rechazar** (paráfrasis alta 4.58 <
negación 7.69 < confirmatorias 9.31). No hay corte posible.

Advertencia de validez: este modelo fue entrenado para relevancia
consulta-pasaje, no para equivalencia entre consultas, y la negación
preserva casi intacta la relevancia temática. Es evidencia contra **este**
modelo para **esta** tarea, no contra los cross-encoders en general.

> **Alcance acotado por §9.7 (agosto 2026).** El título de esta
> subsección afirma más de lo que un solo modelo puede sostener. Un
> segundo cross-encoder, `BAAI/bge-reranker-v2-m3`, **no** reproduce la
> inversión reportada acá: en el contraste primario da AUC 0.7667 en
> español y 0.8222 en inglés, contra 0.3333 y 0.0667 de este modelo. La
> inversión significativa en inglés (p=0.0070) es de `ms-marco-MiniLM`,
> no de los cross-encoders. La conclusión operativa —no cachear— sí se
> sostiene con ambos, pero por motivos distintos. Ver §9.7.

Latencia medida, por si alguien evalúa el costo: 36.4 ms de media por par
—47 pares, recalculable desde el campo `latency_ms` de
`resultados_reranker.json`—, en CPU, cubriendo las dos direcciones y sin
batching. La carga del modelo toma entre 4 y 20 segundos una sola vez,
según esté el caché de disco. No se midió el costo end-to-end de una
consulta completa, así que estas cifras no dicen por sí solas si el paso
de confirmación cabe en un presupuesto de latencia dado.

### 9.5 Correcciones puntuales

- **Resumen ejecutivo.** "las similitudes de paráfrasis se quedan bajo
  0.9060" vale solo para las paráfrasis de bajo solapamiento de la
  primera corrida. Con paráfrasis de alto solapamiento y el mismo
  embedder, el máximo es **0.9745**.
- **§4.1, negación.** Con n=5 el mínimo era 0.9702 — que además
  pertenecía a un par inválido (§9.0). Con el set ampliado y depurado
  (n=9, incorpora inversiones del tipo permitir/prohibir) el mínimo baja
  a **0.9281**. El rango real es más ancho que el publicado.
- **§4.2.** La tabla de conteos a un umbral fijo es inestable con este
  tamaño de muestra y no debe citarse como tasa. Se conserva como
  referencia operativa del default enviado; el reporte válido es el
  barrido completo de umbrales y el AUC.
- **§7.** No se observó no determinismo. Comparando 78 pares entre dos
  corridas independientes, las similitudes coinciden a cuatro decimales
  sin ninguna excepción. Se retira esa advertencia.
- **§9.4 y §9.7, latencia.** Las medias por par salen del campo
  `latency_ms` de los JSON trackeados y son recalculables desde ahí:
  `resultados_reranker.json` da 36.4 ms y `resultados_reranker_bge.json`
  da 571.1 ms, sobre 47 pares cada uno. Versiones anteriores de esas dos
  secciones citaban además una segunda corrida por modelo —32.6 ms para
  MiniLM y 637.0 ms para BGE— cuyo artefacto no está en el repositorio: el
  comando de reproducción documentado redirigía con `>`, así que cada
  corrida pisaba el `.txt` de la anterior y la primera se perdía. Se
  retiran ambas cifras. El multiplicador de §9.7 dependía de una de ellas
  y pasa de ~17.5x a **15.7x**, que es el cociente de las dos medias que
  sí tienen artefacto. El comando ahora escribe un archivo por corrida.

### 9.6 Materiales adicionales

Al corpus y script originales (`pairs.py`, `test_threshold.py`) se suman:

| Archivo | Qué hace |
|---|---|
| `pairs_v3.py` | Corpus ampliado: 31 pares ES, 16 EN, con el mecanismo de negación etiquetado |
| `test_threshold_v4.py` | Barrido de umbrales, AUC, punto de operación seguro; persiste `resultados_v4.json` |
| `analyze_contrasts.py` | Contrastes con solapamiento léxico controlado |
| `significance.py` | Test exacto de permutación sobre AUC y jackknife del margen |
| `test_reranker.py` | Puntuación con cross-encoder en el mismo esquema JSON; `--model` elige cuál (ver §9.7) |

Los archivos `.json` guardan las similitudes crudas: el reanálisis no
requiere recalcular embeddings ni tener Ollama corriendo.

Sobre el corpus: **`pairs_v3.py` no es un superconjunto de `pairs.py`.**
Conserva `neg-01` a `neg-03`, reclasifica `neg-04` y `neg-05` como
`cnf-01` y `cnf-02` por el motivo explicado en §9.0, y agrega seis pares
nuevos de negación que cubren tres mecanismos de inversión de polaridad
(con/sin, incluye/excluye, permite/prohíbe). Los 20 pares originales
siguen disponibles sin cambios en `pairs.py`, de modo que las cifras de
§4 se pueden reproducir tal como fueron publicadas, incluidas las que
§9.0 corrige.

### 9.7 Una predicción registrada, y fallida: BGE-reranker-v2-m3

Antes de correr el segundo cross-encoder se registró una predicción:
`BAAI/bge-reranker-v2-m3` debía quedar **más invertido** que
`ms-marco-MiniLM` en el contraste primario, por entrenar sobre el mismo
objetivo de relevancia consulta-pasaje y con más capacidad para
explotarlo.

**La predicción falla en los dos idiomas.**

| Contraste primario (paráfrasis alta vs negación) | ms-marco-MiniLM | bge-reranker-v2-m3 |
|---|---|---|
| Español | AUC 0.3333, p=0.3636 | AUC **0.7667**, p=0.1174 |
| Inglés | AUC 0.0667, **p=0.0070** | AUC **0.8222**, p=0.0599 |

No solo no está más invertido: queda del otro lado de 0.50 en ambos.

#### Qué se puede afirmar y qué no

Ningún resultado en español alcanza significancia —p=0.1174 para BGE y
p=0.3636 para MiniLM—, así que la distancia entre 0.3333 y 0.7667 **no
se puede reclamar como una diferencia real** a esta n. En inglés BGE
queda en p=0.0599, sin cruzar 0.05.

La afirmación defendible es *"la predicción falla"*. No es *"BGE
funciona"*. Es el mismo freno que §9.3 aplicó a `bge-m3`: cuando los
datos no alcanzan para decidir de qué lado está el efecto, la respuesta
correcta es que no se sabe.

#### La inversión en inglés no replica

El resultado más fuerte de §9.4 —inversión significativa en inglés,
p=0.0070— no aparece con el segundo modelo, que apunta en dirección
contraria. Eso acota el alcance de §9.4 a **`ms-marco-MiniLM`** y le
quita respaldo al salto de "este modelo" a "los cross-encoders", que la
propia §9.4 ya advertía no hacer. La advertencia estaba bien puesta; la
medición ahora la respalda.

#### Observación secundaria: el perfil de falla se repite entre formatos

`bge-reranker-v2-m3` en español da **AUC 1.0000 en temporal y en
entidad** (p=0.0079 en ambos) y no resuelve polaridad. Es el **mismo
perfil** que §9.3 midió para `bge-m3` como bi-encoder: resuelve
limpiamente tiempo y entidad, queda indeterminado en negación.

Dos modelos de la familia m3, dos formatos distintos —bi-encoder y
cross-encoder—, el mismo modo de falla. Sugiere que la limitación sigue
al objetivo de entrenamiento y no al formato de puntuación.

**Se registra como observación, no como conclusión.** Son dos modelos de
una misma familia. No es una muestra de la que se pueda generalizar a
"los modelos entrenados con este objetivo", y quien quiera sostener eso
necesita medirlo sobre modelos de familias distintas.

Los dos p=0.0079 están **en el piso** del test exacto a n=5 vs 5: el
test no puede distinguir ese resultado de cualquier otro igual de
extremo. Es un bit de información, no una medición fina.

#### La conclusión operativa no se mueve

Que BGE no esté invertido no lo vuelve utilizable. En su mejor punto de
operación:

- **Español:** umbral 1.0000 → **3 errores de 14** (1 hit falso, 2 de 5
  hits legítimos perdidos).
- **Inglés:** umbral 1.0000 → **2 errores de 14** (0 falsos, 2 de 5
  legítimos perdidos).
- Contra paráfrasis de bajo solapamiento, el punto que minimiza errores
  vuelve a ser degenerado: rechazar todo, es decir **no cachear**.

Ordenar bien y cortar bien son cosas distintas. Un AUC alto dice que el
orden es correcto; un caché necesita el corte, y el corte no está.

#### Las escalas no son comparables entre modelos

`sentence-transformers` aplica la activación que declara el config de
cada modelo, no una fija:

| Modelo | `activation_fn` | Escala | Rango observado (ES) |
|---|---|---|---|
| `cross-encoder/ms-marco-MiniLM-L-6-v2` | `Identity` | logit crudo, sin acotar | −2.07 a 8.95 |
| `BAAI/bge-reranker-v2-m3` | `Sigmoid` | probabilidad en [0, 1] | 0.1132 a 0.99998 |

**AUC y p-valores sí comparan** entre ambos: dependen solo del orden, y
la sigmoide es monótona. **Los márgenes no.** Cerca de 1.0 la sigmoide
comprime, de modo que un margen de 0.0001 en probabilidad puede
corresponder a una distancia grande en espacio de logit. No leer esos
márgenes como separación, ni citarlos junto a los −6.27 de §9.4.

`test_reranker.py` ahora detecta la activación y la guarda en el JSON
(`activation_fn`, `metric_label`), en vez de afirmar una escala fija
como hacía cuando el modelo estaba hardcodeado.

Sobre la saturación: los `1.0000` de las tablas son **redondeo de
display**. El máximo real es 0.99998 y no hay ningún valor exactamente
igual a 1.0. En el contraste primario en español hay **1 empate exacto
en 45 comparaciones** (AUC 0.7667 con empates, 0.7727 sin ellos) y
**0 empates** en inglés. El AUC no está inflado por el crédito de 0.5
que el cálculo asigna a los empates. Se verificó porque, de haber
saturación real, habría podido fabricar el resultado completo.

#### Latencia

571.1 ms de media por par contra los 36.4 ms de MiniLM: **15.7x**, que es
571.1 / 36.4. Las dos medias se recalculan desde el campo `latency_ms` de
`resultados_reranker_bge.json` y `resultados_reranker.json`, 47 pares cada
una. La carga del modelo toma 8.4 s con caché de disco tibia, y 131 s la
primera vez incluyendo la descarga. CPU, un par a la vez, sin batching,
cubriendo las dos direcciones.

Son 568M de parámetros contra 22M. La cifra es **costo operativo, no
evidencia sobre la hipótesis**: un modelo más caro no está ni más ni
menos invertido por serlo.

#### Materiales

| Archivo | Qué contiene |
|---|---|
| `resultados_reranker_bge.json` | Puntajes crudos de BGE, con `activation_fn` y `metric_label` |
| `resultados_reranker_bge.txt` | Salida completa de la corrida |
| `contrastes_reranker_bge.txt` | Contrastes con solapamiento controlado |
| `significancia_reranker_bge.txt` | Permutación exacta y jackknife |

Reproducible con:

```powershell
# Una corrida, un archivo. La corrida publicada quedó en
# resultados_reranker_bge.txt; para repetir, cambiar el sufijo en vez de
# sobrescribirla — así se puede comparar entre corridas en vez de perder
# la anterior.
python test_reranker.py --model BAAI/bge-reranker-v2-m3 `
    --out resultados_reranker_bge_run2.json > resultados_reranker_bge_run2.txt 2>&1
python analyze_contrasts.py resultados_reranker_bge_run2.json --metric-label "cross-encoder probability (sigmoid)"
python significance.py resultados_reranker_bge_run2.json --metric-label "cross-encoder probability (sigmoid)"
```

El `--out` es la otra mitad: sin él, `test_reranker.py` deriva la ruta del
JSON del `--model` y la reescribe en cada corrida, así que redirigir el
`.txt` a un archivo nuevo salvaría el log y perdería igual los puntajes
crudos. Los archivos sin sufijo son los de la corrida publicada, que es la
que citan las tablas de arriba.

`test_reranker.py` toma `--model` y deriva de él los nombres de scope y
la ruta del JSON, para que dos modelos no se pisen ni se confundan al
releer. Sin argumento sigue escribiendo `resultados_reranker.json`, el
nombre citado en §9.6.

## 10. Trabajos relacionados

### 10.0 Nota de proceso

**Este experimento se diseñó y se corrió sin revisar literatura previa.**
Existe trabajo publicado que anticipa los hallazgos principales: que los
modelos neuronales de recuperación colapsan la negación, que la
arquitectura importa menos de lo que uno esperaría, y que en algunos
dominios la similitud coseno entre un par negado es *más alta* que entre
oraciones que expertos humanos calificaron como equivalentes.

Esto no se presenta como respaldo encontrado después. Se presenta como lo
que es: **una revisión que debió hacerse antes y no se hizo.** Buena
parte de lo que §9.2 y §9.3 llamaron hallazgos son redescubrimientos. Las
mediciones siguen siendo válidas —son propias, reproducibles y están en
el repositorio— pero su novedad es menor que la que el reporte original
sugería, y esta sección existe para corregir esa impresión.

Las referencias de abajo están verificadas. Se citan solo por sus
hallazgos publicados; no se les atribuye ninguna cifra que no aparezca
en ellas.

### 10.1 El fenómeno es conocido

**NevIR** (Weller et al., EACL 2024) plantea la tarea directamente: pide
a modelos de recuperación ordenar dos documentos que difieren únicamente
por una negación. Sus resultados varían por arquitectura —los
cross-encoders quedan mejor, luego los de interacción tardía, y al final
los bi-encoders y las arquitecturas dispersas— pero la conclusión
general es dura: la mayoría de los modelos, incluidos los del estado del
arte, rinden **igual o peor que un ordenamiento aleatorio**. Los
cross-encoders quedan apenas por encima del azar.

Eso encuadra las mediciones de este reporte:

- `nomic-embed-text` es un bi-encoder, y en el contraste primario con
  solapamiento igualado da AUC 0.1333 (§9.1) — invertido, muy por debajo
  del 0.50 del azar. Cae en la categoría que NevIR reporta como la peor.
- Los dos cross-encoders quedan repartidos alrededor del azar: 0.3333
  (ES) y 0.0667 (EN) para `ms-marco-MiniLM` (§9.4); 0.7667 y 0.8222 para
  `bge-reranker-v2-m3` (§9.7). Esa dispersión es **consistente** con un
  desempeño que apenas supera el azar, y explica por qué la predicción
  de §9.7 falló: si la señal real está cerca del azar, el signo de
  cualquier medición individual a esta n es poco informativo.

Verbo deliberado: **consistente**, no *confirma*. La tarea de NevIR
—ordenar dos documentos frente a una consulta— no es la de este reporte
—decidir si dos consultas comparten respuesta—, y las n de acá no
permiten confirmar nada.

**La reproducción de NevIR** (SIGIR 2025) replica el resultado y evalúa
modelos más nuevos, incluyendo el benchmark ExcluIR de consultas
exclusionarias. Encuentra que los rerankers listwise basados en LLM
superan a las demás categorías, pero **siguen por debajo del desempeño
humano**. Es el dato más relevante para cualquiera que piense resolver
esto poniendo un modelo más grande adelante: la dirección ayuda y no
cierra la brecha.

### 10.2 La inversión tampoco es nueva

§9.4 y §9.7 tratan la inversión —pares adversos puntuando *por encima*
de las paráfrasis genuinas— como el resultado más llamativo. No lo es.

Un trabajo de 2021 sobre embeddings de oraciones en el dominio
biomédico (arXiv 2110.15708) reporta el mismo patrón: en **todos** los
modelos evaluados, la similitud coseno promedio de los subconjuntos de
negación y antónimos resultó **más alta** que la del subconjunto de
oraciones calificadas como altamente similares por expertos humanos.

Otro dominio, otro idioma, otros modelos, mismo patrón. Que este reporte
lo haya vuelto a encontrar en español administrativo agrega un punto de
evidencia, no un descubrimiento.

### 10.3 Qué predice HEROS, y una predicción falsable

**HEROS** (arXiv 2306.05083) ofrece la explicación mecánica que §9.2
buscó y no encontró. §9.2 descartó correctamente que el problema fuera
el español, pero se quedó sin causa. HEROS propone una: **el objetivo de
entrenamiento**, no la arquitectura ni el idioma.

Concretamente, encuentra que los encoders ajustados sobre datasets de
paráfrasis con aprendizaje contrastivo son **muy sensibles** a
negaciones y antónimos, porque los datasets tipo NLI tratan la negación
como negativo duro. En cambio, el fine-tuning hecho solo con pares
pregunta-respuesta los vuelve **insensibles** a la negación.

`nomic-embed-text` se entrena mayormente sobre pares de recuperación.
Cae del lado insensible, que es exactamente lo que mide §9.1.

> **Predicción falsable, registrada antes de medir (agosto 2026).** Un
> encoder ajustado sobre NLI debería **separar** el contraste primario
> (paráfrasis alta vs negación, solapamiento igualado) donde
> `nomic-embed-text` no separa: AUC materialmente por encima de 0.50 en
> lugar de 0.1333. Si no separa, HEROS no explica este caso y la causa
> sigue abierta.
>
> **No medido aún.** Se registra acá, con fecha y antes de correr nada,
> por el motivo que §9.7 dejó sentado: una predicción que se escribe
> después de ver el resultado no es una predicción.

### 10.4 Qué no cubre la literatura citada

Descontado todo lo anterior, lo que queda como aporte propio de este
reporte es acotado:

- **El contexto es caché, no ranking.** NevIR y su reproducción miden
  orden de resultados. Un orden malo **degrada** la respuesta y el
  usuario lo ve: los documentos equivocados aparecen y se notan. Un hit
  de caché **omite el LLM por completo** y sirve una respuesta anterior
  con confianza plena y sin señal de que algo salió mal. El fenómeno
  subyacente es el mismo; la consecuencia operativa no lo es, y es la
  que decide si la flag va en `true` o en `false`.
- **La distinción negación / interrogativa negativa confirmatoria**
  (§9.0) es específica del español y no aparece en NevIR, que trabaja en
  inglés. En español "¿No es obligatorio X?" pide confirmar lo mismo que
  "¿Es obligatorio X?", y un caché correcto debe **aceptar** ese par
  mientras rechaza la negación declarativa. Es una categoría que la
  literatura citada no separa.
- **El error de clasificación de §9.0 y el control de solapamiento
  léxico de §9.1** son sobre el proceso de este experimento, no sobre
  los modelos. Que un control mal elegido pueda sostener una conclusión
  correcta por el motivo equivocado es transferible a quien diseñe un
  probe parecido.

Ninguno de los tres es un hallazgo sobre modelos de lenguaje. El primero
es una diferencia de contexto operativo, el segundo una categoría
lingüística que el benchmark existente no cubre, y el tercero una
lección de método. Es el tamaño real del aporte una vez descontada la
literatura, y conviene decirlo así antes que alguien lo diga por uno.

### 10.5 Referencias

1. Weller, O. et al. **"NevIR: Negation in Neural Information
   Retrieval."** EACL 2024, pp. 2274–2287.
   <https://aclanthology.org/2024.eacl-long.139/> — arXiv:2305.07614
2. **"Reproducing NevIR: Negation in Neural Information Retrieval."**
   SIGIR 2025. arXiv:2502.13506
3. **"Revealing the Blind Spot of Sentence Encoder Evaluation by
   HEROS."** arXiv:2306.05083
4. **"Neural sentence embedding models for semantic similarity
   estimation in the biomedical domain."** arXiv:2110.15708

---

*Este reporte es material académico personal. No describe deployment
institucional específico ni utiliza datos de ningún sistema en producción.*
