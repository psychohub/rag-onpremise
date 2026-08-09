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
compatibilidad. Aca NO es un coseno:

  - No esta acotado a [-1, 1]. Es un logit crudo del cross-encoder.
  - No es comparable en escala con los cosenos de resultados_v4.json.
    Los margenes que reporten analyze_contrasts.py y significance.py
    sobre este archivo estan en unidades de logit. NO citarlos junto a
    los margenes en coseno de v4 como si fueran la misma magnitud.
  - El AUC y los p-valores de permutacion SI son comparables entre
    ambos archivos: dependen solo del orden, y cualquier transformacion
    monotona (sigmoide, identidad) los deja intactos.

Por eso este script no hace barrido de umbrales: un umbral fijo sobre
un logit sin acotar no se traslada a otro corpus ni a otro modelo.

CAVEAT DE VALIDEZ DE CONSTRUCTO
--------------------------------
ms-marco-MiniLM-L-6-v2 fue entrenado para relevancia consulta-pasaje,
no para equivalencia entre dos consultas. Puntuar (query, twin) le
pregunta "es twin un pasaje relevante para query", que no es la
pregunta del cache ("tienen estas dos consultas la misma respuesta").
Un resultado pobre aca es evidencia de que ESTE modelo no sirve para
ESTA tarea, no de que los cross-encoders en general no puedan. Decirlo
asi en cualquier reporte derivado.

Uso:
    python test_reranker.py > resultados_reranker.txt 2>&1

Genera: resultados_reranker.json

Luego, sin cambios:
    python analyze_contrasts.py resultados_reranker.json
    python significance.py resultados_reranker.json

Requisitos:
    - pip install sentence-transformers
    - Descarga del modelo desde HuggingFace en la primera corrida.
      Despues queda en cache local y funciona sin red.
    - No requiere Ollama.
"""

import json
import statistics
import sys
import time
from typing import Any, Dict, List

try:
    from sentence_transformers import CrossEncoder
except ImportError:
    print("ERROR: falta 'sentence-transformers'. Instalar con:")
    print("    pip install sentence-transformers")
    sys.exit(1)

from pairs_v3 import PAIRS_ES, PAIRS_EN, CATEGORIES

# -- Configuracion --------------------------------------------
MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"
SHORT_NAME = "ms-marco-MiniLM"
JSON_OUT = "resultados_reranker.json"

SEP_HEAVY = "=" * 74
SEP_LIGHT = "-" * 74


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
              label: str) -> List[Dict[str, Any]]:
    print("")
    print(SEP_HEAVY)
    print(f"Running: {label}  |  Model: {MODEL_NAME}  |  Pairs: {len(pairs)}")
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
            "model": MODEL_NAME,
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
def print_distribution(results: List[Dict[str, Any]], scope: str) -> None:
    print("")
    print(SEP_LIGHT)
    print(f"DISTRIBUTION (mean of both directions) -- {scope}")
    print(SEP_LIGHT)
    print("  Values are unbounded cross-encoder logits, NOT cosines.")
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
def main() -> None:
    print(SEP_HEAVY)
    print("Cross-encoder reranker scoring -- v4-schema compatible")
    print(SEP_HEAVY)
    print(f"Model:        {MODEL_NAME}")
    print(f"Pairs ES/EN:  {len(PAIRS_ES)} / {len(PAIRS_EN)}")
    print(f"Output:       {JSON_OUT}")
    print("")
    print("NOTE: 'similarity' holds the mean of both directions. It is an")
    print("      unbounded logit, not a cosine. Margins derived from it are")
    print("      in logit units and are NOT comparable to resultados_v4.json.")
    print("      AUC and permutation p-values ARE comparable.")

    print("")
    print("Loading model (first run downloads from HuggingFace)...")
    t_load = time.perf_counter()
    try:
        model = CrossEncoder(MODEL_NAME)
    except Exception as e:
        print("")
        print(f"ERROR: no se pudo cargar {MODEL_NAME}")
        print(f"       {type(e).__name__}: {e}")
        print("       Si es la primera corrida, se necesita red para bajar")
        print("       el modelo. Despues queda cacheado y funciona offline.")
        sys.exit(1)
    load_seconds = time.perf_counter() - t_load
    print(f"Loaded in {load_seconds:.2f}s.")

    results_by_scope: Dict[str, List[Dict[str, Any]]] = {}
    results_by_scope[f"ES-{SHORT_NAME}"] = run_pairs(
        model, PAIRS_ES, f"Spanish via {SHORT_NAME}")
    results_by_scope[f"EN-{SHORT_NAME}"] = run_pairs(
        model, PAIRS_EN, f"English via {SHORT_NAME}")

    # -- Persistencia --
    # Va ANTES de cualquier resumen. Leccion de v4: un error de formateo
    # no debe destruir el computo.
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "model": MODEL_NAME,
        "results_by_scope": results_by_scope,
    }
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("")
    print(SEP_HEAVY)
    print(f"Raw scores written to {JSON_OUT}")
    print("Schema matches resultados_v4.json. Run without modification:")
    print(f"    python analyze_contrasts.py {JSON_OUT}")
    print(f"    python significance.py {JSON_OUT}")
    print(SEP_HEAVY)

    # -- Resumenes --
    for scope, results in results_by_scope.items():
        print("")
        print(SEP_HEAVY)
        print(f"SCOPE REPORT: {scope}")
        print(SEP_HEAVY)
        print_distribution(results, scope)
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
