"""
Reranker cross-encoder sobre los mismos pares -- v4-compatible.

Por que existe
--------------
Todo el experimento de umbral hasta ahora midio coseno entre embeddings
independientes. Un cross-encoder no embebe por separado: procesa el par
junto y puede, en principio, representar el alcance de la negacion, que
es exactamente lo que colapsa en nomic-embed-text y queda indeterminado
en bge-m3.

Este script NO decide nada. Solo puntua los mismos pares de pairs_v3 y
escribe el resultado en el mismo esquema JSON que resultados_v4.json,
para que analyze_contrasts.py y significance.py corran encima sin
ninguna modificacion.

Asimetria
---------
Un cross-encoder es asimetrico: score(a, b) != score(b, a). Un cache
semantico necesita una relacion simetrica -- si la consulta A entra
primero o entra segunda no puede cambiar si se sirve la respuesta
cacheada. Por eso se puntua en ambas direcciones y se guardan los tres
valores. La media va en "similarity"; qt y tq quedan crudos para poder
cuantificar la asimetria.

Si la asimetria media es del orden de la separacion entre categorias,
el modelo no sirve como paso de confirmacion simetrica, y eso es un
resultado publicable por si solo -- no un detalle de implementacion.

ADVERTENCIAS SOBRE EL CAMPO "similarity"
----------------------------------------
El nombre es heredado del esquema de v4 y se mantiene por
compatibilidad. Aca NO es un coseno.

LA ESCALA DEPENDE DEL MODELO, y no la elige este script.
sentence-transformers aplica la activacion que el modelo declara en su
config: `CrossEncoder.activation_fn`. Medido:

  - cross-encoder/ms-marco-MiniLM-L-6-v2 -> Identity. Logits crudos sin
    acotar (rango observado en ES: -2.07 a 8.95).
  - BAAI/bge-reranker-v2-m3 -> Sigmoid. Probabilidades en [0, 1]
    (rango observado en ES: 0.1132 a 0.99998).

Consecuencias, y son la razon por la que el script ahora detecta y
registra la activacion en el JSON en vez de afirmar una escala fija:

  - Los margenes NO son comparables entre modelos con activaciones
    distintas, ni con los cosenos de resultados_v4.json. Un margen de
    0.0001 cerca de p=1 no es "casi cero": la sigmoide comprime, y esa
    misma distancia en espacio de logit puede ser grande. No citar
    margenes en probabilidad como si midieran separacion.
  - El AUC y los p-valores de permutacion SI son comparables entre
    todos los archivos: dependen solo del orden, y cualquier
    transformacion monotona (sigmoide, identidad) los deja intactos.
    Es la unica comparacion entre modelos que este esquema soporta.

Por eso este script no hace barrido de umbrales: un umbral fijo sobre
una escala que cambia con el modelo no se traslada a otro corpus ni a
otro modelo.

CAVEAT DE VALIDEZ DE CONSTRUCTO
--------------------------------
Los cross-encoders de reranking se entrenan para relevancia
consulta-pasaje, no para equivalencia entre dos consultas. Puntuar
(query, twin) le pregunta "es twin un pasaje relevante para query", que
no es la pregunta del cache ("tienen estas dos consultas la misma
respuesta"). Un resultado pobre es evidencia de que EL MODELO PUNTUADO
no sirve para ESTA tarea, no de que los cross-encoders en general no
puedan. Decirlo asi en cualquier reporte derivado, nombrando el modelo.

El caveat aplica a cada modelo que se pase por --model, y aplica con
mas fuerza cuanto mas cerca este su objetivo de entrenamiento del de
ms-marco. No se debilita porque el modelo sea mas grande o mas
multilingue.

Uso:
    python test_reranker.py --out resultados_reranker_run2.json \
        > resultados_reranker_run2.txt 2>&1
    python test_reranker.py --model BAAI/bge-reranker-v2-m3 \
        --out resultados_reranker_bge_run2.json \
        > resultados_reranker_bge_run2.txt 2>&1

Una corrida, un archivo. Los nombres sin sufijo son los de la corrida
publicada; correr sin --out y redirigiendo al mismo .txt pisa las dos
salidas de la corrida anterior y deja sin artefacto cualquier cifra que
se haya citado de ella. Ya pasó una vez: ver la nota de latencia en
§9.5 de threshold-safety.md.

El nombre del JSON y los nombres de scope se derivan del modelo, para
que dos corridas con modelos distintos no se pisen ni se confundan al
leer el JSON. Ver MODEL_REGISTRY y derive_names(). Con --out se puede
forzar otra ruta.

Genera: resultados_reranker.json (o el derivado del modelo)

Luego, sin cambios:
    python analyze_contrasts.py <json> --metric-label "cross-encoder logit"
    python significance.py <json> --metric-label "cross-encoder logit"

Requisitos:
    - pip install sentence-transformers
    - Descarga del modelo desde HuggingFace en la primera corrida.
      Despues queda en cache local y funciona sin red.
    - No requiere Ollama.
"""

import argparse
import json
import re
import statistics
import sys
import time
from typing import Any, Dict, List, Tuple

try:
    from sentence_transformers import CrossEncoder
except ImportError:
    print("ERROR: falta 'sentence-transformers'. Instalar con:")
    print("    pip install sentence-transformers")
    sys.exit(1)

from pairs_v3 import PAIRS_ES, PAIRS_EN, CATEGORIES

# -- Configuracion --------------------------------------------
DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Nombres cortos y sufijo de archivo por modelo conocido.
#
# El sufijo del primero es "" a proposito: la corrida original escribio
# resultados_reranker.json y ese nombre esta citado en threshold-safety.md
# §9.6. Cambiarlo romperia la referencia publicada.
#
# Un modelo que no este aca funciona igual: derive_names() arma el nombre
# corto y el sufijo desde el identificador. La tabla solo existe para que
# los modelos ya reportados conserven el nombre con que se publicaron.
MODEL_REGISTRY = {
    "cross-encoder/ms-marco-MiniLM-L-6-v2": ("ms-marco-MiniLM", ""),
    "BAAI/bge-reranker-v2-m3": ("bge-reranker-v2-m3", "_bge"),
}

SEP_HEAVY = "=" * 74
SEP_LIGHT = "-" * 74


def derive_names(model_name: str) -> Tuple[str, str]:
    """
    Devuelve (nombre_corto, ruta_json) para un modelo.

    El nombre corto va en los nombres de scope del JSON ("ES-<corto>"),
    de modo que el scope identifique al modelo que lo produjo. Un scope
    llamado igual para dos modelos distintos haria que analyze_contrasts
    y significance reporten sobre archivos indistinguibles.
    """
    if model_name in MODEL_REGISTRY:
        short, suffix = MODEL_REGISTRY[model_name]
    else:
        short = model_name.split("/")[-1]
        suffix = "_" + re.sub(r"[^0-9a-zA-Z]+", "-", short).strip("-").lower()
    return short, f"resultados_reranker{suffix}.json"


def describe_activation(model: "CrossEncoder") -> Tuple[str, str]:
    """
    Devuelve (nombre_activacion, metric_label) para el modelo cargado.

    No lo elige este script: sentence-transformers resuelve la activacion
    desde el config del modelo. Registrarla es obligatorio, porque decide
    en que escala esta el campo "similarity" y por tanto si los margenes
    de dos corridas son comparables entre si. Ver el docstring.
    """
    fn = getattr(model, "activation_fn", None)
    name = type(fn).__name__ if fn is not None else "unknown"
    labels = {
        "Identity": "cross-encoder logit",
        "Sigmoid": "cross-encoder probability (sigmoid)",
        "Softmax": "cross-encoder probability (softmax)",
    }
    return name, labels.get(name, f"cross-encoder score ({name})")


# -- Puntuacion -----------------------------------------------
def score_pair(model: "CrossEncoder", query: str, twin: str):
    """
    Puntua en ambas direcciones y devuelve (qt, tq, media, latencia_ms).

    La latencia cubre las DOS pasadas, porque un cache que dependa de
    esta senal tendria que pagar ambas para obtener un puntaje
    simetrico.
    """
    t0 = time.perf_counter()
    qt = float(model.predict([(query, twin)])[0])
    tq = float(model.predict([(twin, query)])[0])
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    return qt, tq, (qt + tq) / 2.0, elapsed_ms


def run_pairs(model: "CrossEncoder", pairs: List[Dict[str, Any]],
              label: str, model_name: str) -> List[Dict[str, Any]]:
    print("")
    print(SEP_HEAVY)
    print(f"Running: {label}  |  Model: {model_name}  |  Pairs: {len(pairs)}")
    print(SEP_HEAVY)
    print(f"{'#':>4s}  {'pair':14s} {'category':16s} "
          f"{'qt':>9s} {'tq':>9s} {'mean':>9s} {'|qt-tq|':>9s} {'ms':>8s}")

    results = []
    total = len(pairs)
    t_scope = time.perf_counter()

    for i, pair in enumerate(pairs, 1):
        try:
            qt, tq, mean, ms = score_pair(model, pair["query"], pair["twin"])
        except Exception as e:
            print("")
            print(f"ERROR puntuando el par {pair['id']}: {type(e).__name__}: {e}")
            sys.exit(1)

        results.append({
            "id": pair["id"],
            "category": pair["category"],
            "mechanism": pair.get("mechanism"),
            "language": pair["language"],
            "expected": pair["expected_behavior"],
            "model": model_name,
            "similarity": mean,          # nombre heredado; logit, no coseno
            "score_qt": qt,
            "score_tq": tq,
            "latency_ms": ms,
        })

        print(f"{i:>4d}  {pair['id']:14s} {pair['category']:16s} "
              f"{qt:>9.4f} {tq:>9.4f} {mean:>9.4f} "
              f"{abs(qt - tq):>9.4f} {ms:>8.1f}")

    elapsed = time.perf_counter() - t_scope
    print("")
    print(f"Scope done in {elapsed:.1f}s.")
    return results


# -- Reportes -------------------------------------------------
def print_distribution(results: List[Dict[str, Any]], scope: str,
                       activation: str, metric_label: str) -> None:
    print("")
    print(SEP_LIGHT)
    print(f"DISTRIBUTION (mean of both directions) -- {scope}")
    print(SEP_LIGHT)
    print(f"  Values are {metric_label} (activation: {activation}), "
          f"NOT cosines.")
    if activation == "Identity":
        print("  Unbounded. Margins are in logit units.")
    elif activation in ("Sigmoid", "Softmax"):
        print("  Bounded to [0, 1] and COMPRESSED near the ends: a small")
        print("  numeric gap close to 1.0 can be a large gap in logit space.")
        print("  Do not read these margins as separation.")
    print("")
    print(f"{'category':17s} {'exp':7s} {'n':>3s} {'min':>9s} {'max':>9s} "
          f"{'mean':>9s} {'median':>9s}")

    for cat in CATEGORIES:
        rows = [r for r in results if r["category"] == cat]
        if not rows:
            continue
        sims = [r["similarity"] for r in rows]
        print(f"{cat:17s} {rows[0]['expected']:7s} {len(sims):>3d} "
              f"{min(sims):>9.4f} {max(sims):>9.4f} "
              f"{statistics.mean(sims):>9.4f} {statistics.median(sims):>9.4f}")


def print_asymmetry(results: List[Dict[str, Any]], scope: str) -> None:
    """
    Compara la asimetria direccional contra la dispersion entre
    categorias. Si la primera es del orden de la segunda, el puntaje
    no define una relacion simetrica y el cache no puede usarlo.
    """
    print("")
    print(SEP_LIGHT)
    print(f"DIRECTIONAL ASYMMETRY |score_qt - score_tq| -- {scope}")
    print(SEP_LIGHT)
    print(f"{'category':17s} {'n':>3s} {'min':>9s} {'max':>9s} "
          f"{'mean':>9s} {'median':>9s}")

    for cat in CATEGORIES:
        rows = [r for r in results if r["category"] == cat]
        if not rows:
            continue
        gaps = [abs(r["score_qt"] - r["score_tq"]) for r in rows]
        print(f"{cat:17s} {len(gaps):>3d} "
              f"{min(gaps):>9.4f} {max(gaps):>9.4f} "
              f"{statistics.mean(gaps):>9.4f} {statistics.median(gaps):>9.4f}")

    all_gaps = [abs(r["score_qt"] - r["score_tq"]) for r in results]
    cat_means = [statistics.mean([r["similarity"] for r in results
                                  if r["category"] == c])
                 for c in CATEGORIES
                 if any(r["category"] == c for r in results)]

    print("")
    print(f"  Mean asymmetry over all pairs: {statistics.mean(all_gaps):.4f}")
    print(f"  Max  asymmetry over all pairs: {max(all_gaps):.4f}")

    if len(cat_means) >= 2:
        spread = max(cat_means) - min(cat_means)
        print(f"  Spread between category means: {spread:.4f}")
        if spread > 0:
            ratio = statistics.mean(all_gaps) / spread
            print(f"  Asymmetry / spread ratio:      {ratio:.3f}")
            if ratio >= 1.0:
                print("    -> Direction noise EXCEEDS the between-category signal.")
                print("       The score does not define a symmetric relation.")
            elif ratio >= 0.25:
                print("    -> Direction noise is a large fraction of the signal.")
            else:
                print("    -> Direction noise is small relative to the signal.")


def print_latency(results_by_scope: Dict[str, List[Dict[str, Any]]],
                  load_seconds: float) -> None:
    print("")
    print(SEP_HEAVY)
    print("LATENCY")
    print(SEP_HEAVY)
    print("  Per-pair latency covers BOTH directions, since a symmetric")
    print("  score requires both forward passes.")
    print("")
    print(f"  Model load (once, warm cache): {load_seconds:.2f}s")
    print("")
    print(f"  {'scope':22s} {'n':>4s} {'mean ms':>10s} {'median ms':>11s} "
          f"{'min ms':>9s} {'max ms':>9s}")

    every = []
    for scope, results in results_by_scope.items():
        lat = [r["latency_ms"] for r in results]
        every.extend(lat)
        print(f"  {scope:22s} {len(lat):>4d} {statistics.mean(lat):>10.1f} "
              f"{statistics.median(lat):>11.1f} {min(lat):>9.1f} "
              f"{max(lat):>9.1f}")

    if every:
        print("")
        print(f"  Overall mean per pair: {statistics.mean(every):.1f} ms")
        print(f"  Overall median:        {statistics.median(every):.1f} ms")
        print("")
        print("  Measured on this machine, CPU only, one pair at a time.")
        print("  Batching would lower per-pair cost and is NOT measured here.")


# -- Ejecucion ------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Puntua los pares de pairs_v3 con un cross-encoder.")
    parser.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"Identificador HuggingFace del cross-encoder. "
             f"Default: {DEFAULT_MODEL}")
    parser.add_argument(
        "--out", default=None,
        help="Ruta del JSON de salida. Por defecto se deriva del modelo "
             "(ver derive_names).")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    model_name = args.model
    short_name, derived_out = derive_names(model_name)
    json_out = args.out or derived_out

    print(SEP_HEAVY)
    print("Cross-encoder reranker scoring -- v4-schema compatible")
    print(SEP_HEAVY)
    print(f"Model:        {model_name}")
    print(f"Short name:   {short_name}   (used in scope names)")
    print(f"Pairs ES/EN:  {len(PAIRS_ES)} / {len(PAIRS_EN)}")
    print(f"Output:       {json_out}")
    print("")
    print("NOTE: 'similarity' holds the mean of both directions. It is not a")
    print("      cosine. Its scale depends on the activation the model")
    print("      declares, reported below once the model is loaded. Margins")
    print("      are NOT comparable across activations or to")
    print("      resultados_v4.json. AUC and permutation p-values ARE.")

    print("")
    print("Loading model (first run downloads from HuggingFace)...")
    t_load = time.perf_counter()
    try:
        model = CrossEncoder(model_name)
    except Exception as e:
        print("")
        print(f"ERROR: no se pudo cargar {model_name}")
        print(f"       {type(e).__name__}: {e}")
        print("       Si es la primera corrida, se necesita red para bajar")
        print("       el modelo. Despues queda cacheado y funciona offline.")
        sys.exit(1)
    load_seconds = time.perf_counter() - t_load
    print(f"Loaded in {load_seconds:.2f}s.")

    activation, metric_label = describe_activation(model)
    print("")
    print(f"Activation:   {activation}   (from the model config, not chosen here)")
    print(f"Metric label: {metric_label}")
    if activation not in ("Identity", "Sigmoid", "Softmax"):
        print("WARNING: activacion no reconocida. Verificar la escala antes")
        print("         de comparar margenes con cualquier otra corrida.")

    results_by_scope: Dict[str, List[Dict[str, Any]]] = {}
    results_by_scope[f"ES-{short_name}"] = run_pairs(
        model, PAIRS_ES, f"Spanish via {short_name}", model_name)
    results_by_scope[f"EN-{short_name}"] = run_pairs(
        model, PAIRS_EN, f"English via {short_name}", model_name)

    # -- Persistencia --
    # Va ANTES de cualquier resumen. Leccion de v4: un error de formateo
    # no debe destruir el computo.
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "model": model_name,
        "activation_fn": activation,
        "metric_label": metric_label,
        "results_by_scope": results_by_scope,
    }
    with open(json_out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("")
    print(SEP_HEAVY)
    print(f"Raw scores written to {json_out}")
    print("Schema matches resultados_v4.json. Run without modification:")
    print(f"    python analyze_contrasts.py {json_out} "
          f"--metric-label \"{metric_label}\"")
    print(f"    python significance.py {json_out} "
          f"--metric-label \"{metric_label}\"")
    print(SEP_HEAVY)

    # -- Resumenes --
    for scope, results in results_by_scope.items():
        print("")
        print(SEP_HEAVY)
        print(f"SCOPE REPORT: {scope}")
        print(SEP_HEAVY)
        print_distribution(results, scope, activation, metric_label)
        print_asymmetry(results, scope)

    print_latency(results_by_scope, load_seconds)

    print("")
    print(SEP_HEAVY)
    print("NO threshold sweep and NO separation analysis are done here.")
    print("Both live in analyze_contrasts.py and significance.py, which")
    print("read the JSON above. This script only produces scores.")
    print(SEP_HEAVY)


if __name__ == "__main__":
    main()
