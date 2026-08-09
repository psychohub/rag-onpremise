"""
Experimento de umbral (v4) - separabilidad, no conteos.

Por que existe esta version
---------------------------
Giulio D'Erme senalo que reportar conteos a un umbral fijo ("tres de
cinco superan 0.92") es fragil con muestras chicas, porque los lectores
citan esos conteos como tasas. Su recomendacion fue reportar
distribuciones y la mejor separacion alcanzable a traves de todos los
umbrales.

v3 no hizo eso: construyo una matriz de decision al umbral vigente, que
es exactamente la forma que el habia desaconsejado. v4 corrige el
registro del reporte.

Que cambia respecto de v3
-------------------------
1. BARRIDO DE UMBRALES. En vez de evaluar un umbral, se evalua todo el
   rango y se reporta el mejor desempeno alcanzable. La pregunta pasa
   de "que tan mal le va a 0.92" a "que tan bien puede irle en el mejor
   caso".
2. AUC. Medida de separabilidad independiente de umbral (probabilidad
   de que una parafrasis puntue mas alto que un par adverso tomados al
   azar). 0.50 = ninguna separabilidad. Es la respuesta directa a "la
   mejor separacion alcanzable".
3. PUNTO DE OPERACION SEGURO. Umbral mas bajo que produce CERO hits
   falsos, y cuantos hits legitimos sobreviven ahi. Si sobreviven cero,
   el cache no tiene configuracion util.
4. PERSISTENCIA JSON. Las similitudes se guardan en un archivo, para
   poder reanalizar sin recalcular 156 embeddings.
5. La matriz de decision a umbral fijo sigue disponible pero degradada
   a seccion de diagnostico, con el n visible, y no encabeza el reporte.

Uso:
    python test_threshold_v4.py > resultados_v4.txt 2>&1

Genera ademas: resultados_v4.json

Requisitos:
    - Ollama corriendo en http://localhost:11434
    - ollama pull nomic-embed-text
    - ollama pull bge-m3
    - Python 3.9+ con requests
"""

import json
import math
import sys
import time
import statistics
from typing import List, Dict, Any, Optional, Tuple

try:
    import requests
except ImportError:
    print("ERROR: falta el paquete 'requests'. Instalar con:")
    print("    pip install requests")
    sys.exit(1)

from pairs_v3 import PAIRS_ES, PAIRS_EN, CATEGORIES

# -- Configuracion --------------------------------------------
OLLAMA_URL = "http://localhost:11434"
LEGACY_THRESHOLD = 0.92          # solo para la seccion de diagnostico
TIMEOUT_SECONDS = 60

EMBEDDERS_ES = ["nomic-embed-text", "bge-m3"]
EMBEDDER_EN = "nomic-embed-text"

SWEEP_START = 0.50
SWEEP_END = 1.00
SWEEP_STEP = 0.005

JSON_OUT = "resultados_v4.json"

SEP_HEAVY = "=" * 74
SEP_LIGHT = "-" * 74


# -- Utilidades -----------------------------------------------
def get_embedding(text: str, model: str) -> List[float]:
    response = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": model, "prompt": text},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()["embedding"]


def cosine_similarity(a: List[float], b: List[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    denom = norm_a * norm_b
    return dot / denom if denom > 0 else 0.0


def check_ollama() -> None:
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        r.raise_for_status()
        available = {m["name"].split(":")[0] for m in r.json().get("models", [])}
        missing = set(EMBEDDERS_ES + [EMBEDDER_EN]) - available
        if missing:
            print("")
            print(f"ERROR: faltan modelos en Ollama: {sorted(missing)}")
            for m in sorted(missing):
                print(f"    ollama pull {m}")
            sys.exit(1)
    except SystemExit:
        raise
    except Exception as e:
        print("")
        print(f"ERROR: no se puede conectar a Ollama en {OLLAMA_URL}")
        print(f"       {type(e).__name__}: {e}")
        sys.exit(1)


def run_pairs(pairs: List[Dict[str, Any]], model: str, label: str) -> List[Dict[str, Any]]:
    print("")
    print(SEP_HEAVY)
    print(f"Running: {label}  |  Model: {model}  |  Pairs: {len(pairs)}")
    print(SEP_HEAVY)

    results = []
    t0 = time.time()
    total = len(pairs)

    for i, pair in enumerate(pairs, 1):
        try:
            emb_query = get_embedding(pair["query"], model)
            emb_twin = get_embedding(pair["twin"], model)
        except Exception as e:
            print("")
            print(f"ERROR en par {pair['id']} con {model}: {e}")
            sys.exit(1)

        sim = cosine_similarity(emb_query, emb_twin)
        results.append({
            "id": pair["id"],
            "category": pair["category"],
            "mechanism": pair.get("mechanism"),
            "language": pair["language"],
            "expected": pair["expected_behavior"],
            "model": model,
            "similarity": sim,
        })
        print(f"[{i:2d}/{total}] {pair['id']:14s} ({pair['category']:16s}) sim = {sim:.4f}")

    elapsed = time.time() - t0
    print("")
    print(f"Done in {elapsed:.1f}s ({elapsed / total:.2f}s per pair).")
    return results


# -- Analisis -------------------------------------------------
def split_scores(results: List[Dict[str, Any]],
                 exclude: Optional[List[str]] = None) -> Tuple[List[float], List[float]]:
    """Devuelve (scores de pares accept, scores de pares reject)."""
    exclude = exclude or []
    accept = [r["similarity"] for r in results
              if r["expected"] == "accept" and r["category"] not in exclude]
    reject = [r["similarity"] for r in results
              if r["expected"] == "reject" and r["category"] not in exclude]
    return accept, reject


def auc(accept: List[float], reject: List[float]) -> Optional[float]:
    """
    Probabilidad de que un par accept puntue por encima de uno reject.
    0.50 = ninguna separabilidad. 1.00 = separacion perfecta.
    Valores por debajo de 0.50 indican separacion INVERTIDA: los pares
    que deben rechazarse puntuan mas alto que los que deben aceptarse.
    """
    if not accept or not reject:
        return None
    wins = 0.0
    for a in accept:
        for r in reject:
            if a > r:
                wins += 1.0
            elif a == r:
                wins += 0.5
    return wins / (len(accept) * len(reject))


def sweep(accept: List[float], reject: List[float]) -> List[Dict[str, Any]]:
    """Evalua todo el rango de umbrales."""
    rows = []
    t = SWEEP_START
    n_total = len(accept) + len(reject)
    while t <= SWEEP_END + 1e-9:
        true_hits = sum(1 for s in accept if s >= t)     # correcto: sirve cache
        missed = len(accept) - true_hits                  # inutil, no peligroso
        false_hits = sum(1 for s in reject if s >= t)     # PELIGROSO
        correct_rejects = len(reject) - false_hits
        rows.append({
            "threshold": round(t, 4),
            "true_hits": true_hits,
            "missed_hits": missed,
            "false_hits": false_hits,
            "correct_rejects": correct_rejects,
            "accuracy": (true_hits + correct_rejects) / n_total if n_total else 0.0,
        })
        t += SWEEP_STEP
    return rows


def print_sweep_report(results: List[Dict[str, Any]], scope: str,
                       exclude: Optional[List[str]] = None) -> Dict[str, Any]:
    exclude = exclude or []
    tag = "ALL adverse categories" if not exclude else f"EXCLUDING {', '.join(exclude)}"

    accept, reject = split_scores(results, exclude)
    print("")
    print(SEP_LIGHT)
    print(f"THRESHOLD SWEEP -- {scope}  [{tag}]")
    print(SEP_LIGHT)

    if not accept or not reject:
        print("  (this scope lacks both accept and reject pairs)")
        return {}

    print(f"  n accept (should hit) = {len(accept)}   "
          f"n reject (should not hit) = {len(reject)}")

    a = auc(accept, reject)
    print(f"  AUC = {a:.4f}", end="")
    if a < 0.5:
        print("   <-- INVERTED: adverse pairs score higher than paraphrases")
    elif a < 0.6:
        print("   <-- essentially no separability")
    else:
        print("")

    rows = sweep(accept, reject)

    best = max(rows, key=lambda r: r["accuracy"])
    print("")
    print(f"  Best achievable accuracy: {best['accuracy']:.3f} at threshold "
          f"{best['threshold']:.3f}")
    print(f"    true hits {best['true_hits']}/{len(accept)}   "
          f"false hits {best['false_hits']}/{len(reject)}")

    # Punto de operacion seguro: cero hits falsos
    zero_fp = [r for r in rows if r["false_hits"] == 0]
    if zero_fp:
        safest = min(zero_fp, key=lambda r: r["threshold"])
        print("")
        print(f"  Lowest threshold with ZERO false hits: {safest['threshold']:.3f}")
        print(f"    legitimate hits surviving there: "
              f"{safest['true_hits']}/{len(accept)}")
        if safest["true_hits"] == 0:
            print("    -> the cache never helps at any safe threshold.")
    else:
        print("")
        print("  No threshold in the swept range produces zero false hits.")

    # Tabla resumida
    print("")
    print(f"  {'thr':>6s} {'true':>6s} {'missed':>7s} {'FALSE':>6s} {'acc':>6s}")
    t = 0.70
    while t <= 1.0 + 1e-9:
        row = min(rows, key=lambda r: abs(r["threshold"] - t))
        mark = "  <<" if row["threshold"] == best["threshold"] else ""
        print(f"  {row['threshold']:>6.3f} {row['true_hits']:>6d} "
              f"{row['missed_hits']:>7d} {row['false_hits']:>6d} "
              f"{row['accuracy']:>6.3f}{mark}")
        t += 0.02

    return {
        "auc": a,
        "best": best,
        "zero_false_hit_threshold": (min(zero_fp, key=lambda r: r["threshold"])
                                     if zero_fp else None),
        "n_accept": len(accept),
        "n_reject": len(reject),
    }


def print_distribution(results: List[Dict[str, Any]], scope: str) -> None:
    print("")
    print(SEP_LIGHT)
    print(f"DISTRIBUTION -- {scope}")
    print(SEP_LIGHT)
    print(f"{'category':17s} {'exp':7s} {'n':>3s} {'min':>8s} {'max':>8s} "
          f"{'mean':>8s} {'median':>8s}")
    for cat in CATEGORIES:
        rows = [r for r in results if r["category"] == cat]
        if not rows:
            continue
        sims = [r["similarity"] for r in rows]
        print(f"{cat:17s} {rows[0]['expected']:7s} {len(sims):>3d} "
              f"{min(sims):>8.4f} {max(sims):>8.4f} "
              f"{statistics.mean(sims):>8.4f} {statistics.median(sims):>8.4f}")


def print_mechanism_breakdown(results: List[Dict[str, Any]], scope: str) -> None:
    neg = [r for r in results if r["category"] == "negation"]
    if not neg:
        return
    print("")
    print(SEP_LIGHT)
    print(f"NEGATION BY MECHANISM -- {scope}")
    print(SEP_LIGHT)
    print("  CAVEAT: mechanisms differ in lexical overlap as well as in")
    print("  polarity. with_without changes a function word; permit_prohibit")
    print("  changes a content word. Lower similarity in the latter may be")
    print("  lexical, not semantic. Do not report as a finding.")
    print("")
    print(f"{'mechanism':20s} {'n':>3s} {'min':>8s} {'max':>8s} {'mean':>8s}")
    mechs = []
    for r in neg:
        m = r["mechanism"] or "unspecified"
        if m not in mechs:
            mechs.append(m)
    for m in mechs:
        sims = [r["similarity"] for r in neg if (r["mechanism"] or "unspecified") == m]
        print(f"{m:20s} {len(sims):>3d} {min(sims):>8.4f} "
              f"{max(sims):>8.4f} {statistics.mean(sims):>8.4f}")


def print_legacy_diagnostic(results: List[Dict[str, Any]], scope: str) -> None:
    print("")
    print(SEP_LIGHT)
    print(f"DIAGNOSTIC ONLY -- behaviour at legacy threshold {LEGACY_THRESHOLD}")
    print(SEP_LIGHT)
    print("  Operational reference for the shipped default. NOT a result:")
    print("  per-category counts at a single threshold are unstable at this")
    print("  sample size. Cite the sweep and AUC above instead.")
    print("")
    print(f"{'category':17s} {'exp':7s} {'n':>3s} {'hits':>5s}")
    for cat in CATEGORIES:
        rows = [r for r in results if r["category"] == cat]
        if not rows:
            continue
        hits = sum(1 for r in rows if r["similarity"] >= LEGACY_THRESHOLD)
        print(f"{cat:17s} {rows[0]['expected']:7s} {len(rows):>3d} {hits:>5d}")


# -- Ejecucion ------------------------------------------------
def main() -> None:
    total_embeddings = len(PAIRS_ES) * 2 * len(EMBEDDERS_ES) + len(PAIRS_EN) * 2

    print(SEP_HEAVY)
    print("Threshold separability experiment v4")
    print(SEP_HEAVY)
    print(f"Ollama URL:        {OLLAMA_URL}")
    print(f"Embedders (ES):    {', '.join(EMBEDDERS_ES)}")
    print(f"Embedder (EN):     {EMBEDDER_EN}")
    print(f"Pairs ES / EN:     {len(PAIRS_ES)} / {len(PAIRS_EN)}")
    print(f"Total embeddings:  {total_embeddings}")
    print(f"Sweep range:       {SWEEP_START} to {SWEEP_END} step {SWEEP_STEP}")

    check_ollama()

    results_by_scope: Dict[str, List[Dict[str, Any]]] = {}
    for embedder in EMBEDDERS_ES:
        results_by_scope[f"ES-{embedder}"] = run_pairs(
            PAIRS_ES, embedder, f"Spanish via {embedder}")
    results_by_scope[f"EN-{EMBEDDER_EN}"] = run_pairs(
        PAIRS_EN, EMBEDDER_EN, f"English via {EMBEDDER_EN}")

    summary: Dict[str, Any] = {}
    for label, results in results_by_scope.items():
        print("")
        print(SEP_HEAVY)
        print(f"SCOPE REPORT: {label}")
        print(SEP_HEAVY)
        print_distribution(results, label)
        print_mechanism_breakdown(results, label)
        s_all = print_sweep_report(results, label, [])
        s_noneg = print_sweep_report(results, label, ["negation"])
        print_legacy_diagnostic(results, label)
        summary[label] = {"all": s_all, "no_negation": s_noneg}

    # -- Persistencia --
    # Va ANTES del resumen: las similitudes cuestan 156 embeddings y un
    # fallo al formatear el reporte no debe destruirlas.
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "embedders_es": EMBEDDERS_ES,
        "embedder_en": EMBEDDER_EN,
        "sweep": {"start": SWEEP_START, "end": SWEEP_END, "step": SWEEP_STEP},
        "results_by_scope": results_by_scope,
    }
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("")
    print(SEP_HEAVY)
    print(f"Raw similarities written to {JSON_OUT}")
    print("Re-analysis does not require recomputing embeddings.")
    print(SEP_HEAVY)

    # -- Resumen ejecutivo --
    print("")
    print(SEP_HEAVY)
    print("EXECUTIVE SUMMARY -- separability, threshold-free")
    print(SEP_HEAVY)
    print("")
    print(f"  {'scope':26s} {'AUC all':>9s} {'AUC no-neg':>11s} {'best acc':>9s}")
    def fmt(value: Optional[float], width: int, digits: int) -> str:
        """n/a cuando el scope no tiene ambos lados; nunca formatear None."""
        return f"{'n/a':>{width}s}" if value is None else f"{value:>{width}.{digits}f}"

    for label, s in summary.items():
        a_all = s["all"].get("auc")
        a_non = s["no_negation"].get("auc")
        best = s["all"].get("best", {}).get("accuracy")
        print(f"  {label:26s} "
              f"{fmt(a_all, 9, 4)} "
              f"{fmt(a_non, 11, 4)} "
              f"{fmt(best, 9, 3)}")

    print("")
    print("  Reading guide:")
    print("    AUC 0.50 = the score carries no information about which pairs")
    print("    should be cached. Below 0.50 = the score is actively")
    print("    misleading: adverse pairs rank above genuine paraphrases.")
    print("    Compare AUC all vs AUC no-neg to see how much of the failure")
    print("    is polarity alone.")
    print("    n/a = the scope lacks pairs on one side of the comparison.")


if __name__ == "__main__":
    main()
