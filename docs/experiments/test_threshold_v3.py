"""
Experimento de umbral (v3) - cross-embedder + cross-language.

Cambios respecto de test_threshold_v2.py
----------------------------------------
1. Las categorias se importan desde pairs_v3 en lugar de estar
   hardcodeadas. En v2, agregar una categoria nueva al archivo de
   pares hacia que el reporte la omitiera en silencio.
2. Salida 100% ASCII. La version v2 fallaba en Windows con
   UnicodeEncodeError al redirigir stdout bajo codec cp1252.
3. Desglose por "mechanism" dentro de negacion (with_without,
   include_exclude, permit_prohibit), para reportar si el colapso
   depende del tipo de inversion de polaridad.
4. Analisis de umbral en dos variantes: sobre TODOS los pares
   adversos, y EXCLUYENDO negacion. Esa segunda variante es la que
   revela si un embedder resuelve temporal/entidad pero falla solo
   en polaridad.
5. Matriz de decision al umbral vigente: por categoria, cuantos
   pares se comportarian bien y cuantos mal.

Uso:
    python test_threshold_v3.py > resultados_v3.txt 2>&1

Requisitos:
    - Ollama corriendo en http://localhost:11434
    - ollama pull nomic-embed-text
    - ollama pull bge-m3
    - Python 3.9+ con requests
"""

import math
import sys
import time
import statistics
from typing import List, Dict, Any

try:
    import requests
except ImportError:
    print("ERROR: falta el paquete 'requests'. Instalar con:")
    print("    pip install requests")
    sys.exit(1)

from pairs_v3 import PAIRS_ES, PAIRS_EN, CATEGORIES

# -- Configuracion --------------------------------------------
OLLAMA_URL = "http://localhost:11434"
CURRENT_THRESHOLD = 0.92
TIMEOUT_SECONDS = 60

EMBEDDERS_ES = ["nomic-embed-text", "bge-m3"]
EMBEDDER_EN = "nomic-embed-text"

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
        tags = r.json()
        available = {m["name"].split(":")[0] for m in tags.get("models", [])}
        required = set(EMBEDDERS_ES + [EMBEDDER_EN])
        missing = required - available
        if missing:
            print("")
            print(f"ERROR: faltan modelos en Ollama: {sorted(missing)}")
            print("       Descargar con:")
            for m in sorted(missing):
                print(f"           ollama pull {m}")
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
        expected = pair["expected_behavior"]
        would_hit = sim >= CURRENT_THRESHOLD
        correct = (would_hit and expected == "accept") or (
            not would_hit and expected == "reject"
        )

        results.append({
            "id": pair["id"],
            "category": pair["category"],
            "mechanism": pair.get("mechanism"),
            "language": pair["language"],
            "expected": expected,
            "model": model,
            "similarity": sim,
            "would_hit": would_hit,
            "correct_at_current": correct,
        })

        flag = "ok " if correct else "BAD"
        print(f"[{i:2d}/{total}] {pair['id']:14s} ({pair['category']:16s}) "
              f"sim = {sim:.4f}  {flag}")

    elapsed = time.time() - t0
    print("")
    print(f"Done in {elapsed:.1f}s ({elapsed / total:.2f}s per pair).")
    return results


# -- Reportes -------------------------------------------------
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
        exp = rows[0]["expected"]
        print(f"{cat:17s} {exp:7s} {len(sims):>3d} "
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
    print(f"{'mechanism':20s} {'n':>3s} {'min':>8s} {'max':>8s} {'mean':>8s}")

    mechanisms = []
    for r in neg:
        m = r["mechanism"] or "unspecified"
        if m not in mechanisms:
            mechanisms.append(m)

    for m in mechanisms:
        sims = [r["similarity"] for r in neg
                if (r["mechanism"] or "unspecified") == m]
        print(f"{m:20s} {len(sims):>3d} {min(sims):>8.4f} "
              f"{max(sims):>8.4f} {statistics.mean(sims):>8.4f}")


def separation(results: List[Dict[str, Any]], exclude: List[str] = None):
    """Devuelve (max_adverso, min_aceptable, gap) o None si falta un lado."""
    exclude = exclude or []
    adverse = [r for r in results
               if r["expected"] == "reject" and r["category"] not in exclude]
    accept = [r for r in results
              if r["expected"] == "accept" and r["category"] not in exclude]
    if not adverse or not accept:
        return None
    max_adverse = max(r["similarity"] for r in adverse)
    min_accept = min(r["similarity"] for r in accept)
    return max_adverse, min_accept, min_accept - max_adverse


def print_threshold_analysis(results: List[Dict[str, Any]], scope: str) -> None:
    print("")
    print(SEP_LIGHT)
    print(f"SAFE THRESHOLD ANALYSIS -- {scope}")
    print(SEP_LIGHT)

    scenarios = [
        ("ALL adverse categories", []),
        ("EXCLUDING negation", ["negation"]),
    ]

    for name, exclude in scenarios:
        res = separation(results, exclude)
        print("")
        print(f"  Scenario: {name}")
        if res is None:
            print("    (this scope lacks both reject and accept pairs)")
            continue
        max_adverse, min_accept, gap = res
        print(f"    Highest adverse similarity (should NOT hit): {max_adverse:.4f}")
        print(f"    Lowest accept similarity   (SHOULD hit):     {min_accept:.4f}")
        if gap > 0:
            safe = (max_adverse + min_accept) / 2
            print(f"    SAFE THRESHOLD EXISTS: {safe:.4f}  (gap: {gap:+.4f})")
            if gap < 0.02:
                print("    NOTE: gap is under 0.02 -- within noise at this sample size.")
        else:
            print(f"    NO SAFE THRESHOLD EXISTS  (gap: {gap:+.4f})")


def print_decision_matrix(results: List[Dict[str, Any]], scope: str) -> None:
    print("")
    print(SEP_LIGHT)
    print(f"DECISION MATRIX AT CURRENT THRESHOLD ({CURRENT_THRESHOLD}) -- {scope}")
    print(SEP_LIGHT)
    print(f"{'category':17s} {'exp':7s} {'n':>3s} {'hits':>5s} {'correct':>8s} {'wrong':>6s}")

    total_wrong = 0
    for cat in CATEGORIES:
        rows = [r for r in results if r["category"] == cat]
        if not rows:
            continue
        hits = sum(1 for r in rows if r["would_hit"])
        correct = sum(1 for r in rows if r["correct_at_current"])
        wrong = len(rows) - correct
        total_wrong += wrong
        print(f"{cat:17s} {rows[0]['expected']:7s} {len(rows):>3d} "
              f"{hits:>5d} {correct:>8d} {wrong:>6d}")

    print("")
    print(f"  Total pairs handled incorrectly at {CURRENT_THRESHOLD}: "
          f"{total_wrong} / {len(results)}")


def print_cross_comparison(results_by_scope: Dict[str, List[Dict]]) -> None:
    print("")
    print(SEP_HEAVY)
    print("CROSS COMPARISON -- same pairs, different embedders / languages")
    print(SEP_HEAVY)

    all_ids = []
    seen = set()
    id_to_cat = {}
    for results in results_by_scope.values():
        for r in results:
            if r["id"] not in seen:
                all_ids.append(r["id"])
                seen.add(r["id"])
                id_to_cat[r["id"]] = r["category"]

    scope_labels = list(results_by_scope.keys())
    header = f"{'pair':14s} {'category':17s}"
    for s in scope_labels:
        header += f" {s[:18]:>18s}"
    print(header)
    print("-" * len(header))

    for pair_id in all_ids:
        row_values = {}
        for scope, results in results_by_scope.items():
            match = next((r for r in results if r["id"] == pair_id), None)
            if match:
                row_values[scope] = match["similarity"]

        row = f"{pair_id:14s} {id_to_cat[pair_id]:17s}"
        for s in scope_labels:
            v = row_values.get(s)
            row += f" {v:>18.4f}" if v is not None else f" {'-':>18s}"
        print(row)


# -- Ejecucion ------------------------------------------------
def main() -> None:
    total_embeddings = len(PAIRS_ES) * 2 * len(EMBEDDERS_ES) + len(PAIRS_EN) * 2

    print(SEP_HEAVY)
    print("Threshold safety experiment v3 -- cross-embedder + cross-language")
    print(SEP_HEAVY)
    print(f"Ollama URL:        {OLLAMA_URL}")
    print(f"Current threshold: {CURRENT_THRESHOLD}")
    print(f"Embedders (ES):    {', '.join(EMBEDDERS_ES)}")
    print(f"Embedder (EN):     {EMBEDDER_EN}")
    print(f"Pairs ES:          {len(PAIRS_ES)}")
    print(f"Pairs EN:          {len(PAIRS_EN)}")
    print(f"Total embeddings:  {total_embeddings}")

    check_ollama()

    results_by_scope: Dict[str, List[Dict[str, Any]]] = {}

    for embedder in EMBEDDERS_ES:
        label = f"ES-{embedder}"
        results_by_scope[label] = run_pairs(
            PAIRS_ES, embedder, f"Spanish via {embedder}")

    label_en = f"EN-{EMBEDDER_EN}"
    results_by_scope[label_en] = run_pairs(
        PAIRS_EN, EMBEDDER_EN, f"English via {EMBEDDER_EN}")

    for label, results in results_by_scope.items():
        print("")
        print(SEP_HEAVY)
        print(f"SCOPE REPORT: {label}")
        print(SEP_HEAVY)
        print_distribution(results, label)
        print_mechanism_breakdown(results, label)
        print_threshold_analysis(results, label)
        print_decision_matrix(results, label)

    print_cross_comparison(results_by_scope)

    # -- Resumen ejecutivo --
    print("")
    print(SEP_HEAVY)
    print("EXECUTIVE SUMMARY")
    print(SEP_HEAVY)

    print("")
    print("Negation similarity across scopes:")
    for scope, results in results_by_scope.items():
        sims = [r["similarity"] for r in results if r["category"] == "negation"]
        if sims:
            print(f"  {scope:26s} n={len(sims):<3d} min={min(sims):.4f}  "
                  f"max={max(sims):.4f}  mean={statistics.mean(sims):.4f}")

    print("")
    print("High-overlap paraphrase similarity across scopes (control):")
    for scope, results in results_by_scope.items():
        sims = [r["similarity"] for r in results
                if r["category"] == "paraphrase-high"]
        if sims:
            print(f"  {scope:26s} n={len(sims):<3d} min={min(sims):.4f}  "
                  f"max={max(sims):.4f}  mean={statistics.mean(sims):.4f}")

    print("")
    print("Threshold viability per scope:")
    for scope, results in results_by_scope.items():
        all_res = separation(results, [])
        no_neg = separation(results, ["negation"])
        all_txt = f"{all_res[2]:+.4f}" if all_res else "n/a"
        neg_txt = f"{no_neg[2]:+.4f}" if no_neg else "n/a"
        print(f"  {scope:26s} gap(all)={all_txt:>8s}   gap(no negation)={neg_txt:>8s}")

    print("")
    print("How to read this:")
    print("  gap > 0  means a cosine threshold separates reject from accept.")
    print("  If gap(all) < 0 but gap(no negation) > 0, the embedder handles")
    print("  temporal and entity distinctions but collapses polarity.")
    print("  Compare ES-nomic vs ES-bge-m3 to isolate the EMBEDDER.")
    print("  Compare ES-nomic vs EN-nomic to isolate the LANGUAGE.")

    print("")
    print(SEP_HEAVY)
    print("Save this output. It is the evidence for the next article.")
    print(SEP_HEAVY)


if __name__ == "__main__":
    main()
