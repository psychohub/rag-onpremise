"""
Experimento: ¿es 0.92 un umbral seguro para el caché semántico
sobre texto administrativo en español, con nomic-embed-text?

Corre localmente contra Ollama. No requiere red externa.
No usa queries reales de ningún sistema en producción.

Uso:
    python test_threshold.py

Requisitos:
    - Ollama corriendo en http://localhost:11434
    - Modelo nomic-embed-text descargado: ollama pull nomic-embed-text
    - Python 3.9+
    - Dependencia única: requests (pip install requests)
"""

import math
import sys
import time
import statistics
from typing import List

try:
    import requests
except ImportError:
    print("ERROR: falta el paquete 'requests'. Instalalo con:")
    print("    pip install requests")
    sys.exit(1)

from pairs import PAIRS

# ── Configuración ─────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434"
EMBEDDING_MODEL = "nomic-embed-text"
CURRENT_THRESHOLD = 0.92  # el umbral que estamos probando
TIMEOUT_SECONDS = 30


# ── Utilidades ────────────────────────────────────────────────
def get_embedding(text: str) -> List[float]:
    """Llama a Ollama y devuelve el embedding del texto."""
    response = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={"model": EMBEDDING_MODEL, "prompt": text},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()["embedding"]


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Similitud coseno entre dos vectores. Igual que RagService.cs."""
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    denom = norm_a * norm_b
    return dot / denom if denom > 0 else 0.0


# ── Ejecución ─────────────────────────────────────────────────
def main() -> None:
    print("=" * 70)
    print("Threshold safety experiment for semantic cache")
    print(f"Model: {EMBEDDING_MODEL}   |   Current threshold: {CURRENT_THRESHOLD}")
    print(f"Pairs: {len(PAIRS)}   |   Total embeddings: {len(PAIRS) * 2}")
    print("=" * 70)

    # 1. Comprobar conexión con Ollama
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        r.raise_for_status()
    except Exception as e:
        print(f"\nERROR: no se puede conectar a Ollama en {OLLAMA_URL}")
        print(f"       {type(e).__name__}: {e}")
        print("       Verificá que Ollama esté corriendo.")
        sys.exit(1)

    # 2. Calcular embeddings y similitudes
    results = []
    t0 = time.time()

    for i, pair in enumerate(PAIRS, 1):
        try:
            emb_query = get_embedding(pair["query"])
            emb_twin = get_embedding(pair["twin"])
        except Exception as e:
            print(f"\nERROR obteniendo embedding para par {pair['id']}: {e}")
            sys.exit(1)

        sim = cosine_similarity(emb_query, emb_twin)
        would_hit = sim >= CURRENT_THRESHOLD
        correct = (would_hit and pair["expected_behavior"] == "accept") or (
            not would_hit and pair["expected_behavior"] == "reject"
        )

        results.append(
            {
                "id": pair["id"],
                "category": pair["category"],
                "expected": pair["expected_behavior"],
                "similarity": sim,
                "would_hit": would_hit,
                "correct": correct,
                "query": pair["query"],
                "twin": pair["twin"],
            }
        )

        print(f"[{i:2d}/{len(PAIRS)}] {pair['id']} ({pair['category']:10s}) sim = {sim:.4f}")

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s ({elapsed/len(PAIRS):.2f}s per pair).")

    # 3. Análisis por categoría
    print("\n" + "=" * 70)
    print("SIMILARITY DISTRIBUTION BY CATEGORY")
    print("=" * 70)

    categories = ["negation", "temporal", "entity", "paraphrase"]
    for cat in categories:
        sims = [r["similarity"] for r in results if r["category"] == cat]
        if not sims:
            continue
        print(
            f"{cat:12s}  n={len(sims):2d}  "
            f"min={min(sims):.4f}  "
            f"max={max(sims):.4f}  "
            f"mean={statistics.mean(sims):.4f}  "
            f"median={statistics.median(sims):.4f}"
        )

    # 4. Análisis crítico — falsos positivos y falsos negativos
    print("\n" + "=" * 70)
    print(f"CACHE BEHAVIOR AT THRESHOLD = {CURRENT_THRESHOLD}")
    print("=" * 70)

    false_positives = [
        r for r in results
        if r["expected"] == "reject" and r["would_hit"]
    ]
    false_negatives = [
        r for r in results
        if r["expected"] == "accept" and not r["would_hit"]
    ]

    print(f"\nFalse positives (cache would serve WRONG answer): {len(false_positives)}")
    for fp in false_positives:
        print(f"  [{fp['category']:10s}] sim={fp['similarity']:.4f}  {fp['id']}")
        print(f"    Q: {fp['query']}")
        print(f"    T: {fp['twin']}")

    print(f"\nFalse negatives (cache misses genuine paraphrase): {len(false_negatives)}")
    for fn in false_negatives:
        print(f"  [{fn['category']:10s}] sim={fn['similarity']:.4f}  {fn['id']}")

    # 5. Cuál sería el umbral seguro
    print("\n" + "=" * 70)
    print("SAFE THRESHOLD ANALYSIS")
    print("=" * 70)

    max_adverse = max(
        (r["similarity"] for r in results if r["expected"] == "reject"),
        default=None,
    )
    min_paraphrase = min(
        (r["similarity"] for r in results if r["expected"] == "accept"),
        default=None,
    )

    print(f"Highest similarity among adverse pairs  (should NOT hit): {max_adverse:.4f}")
    print(f"Lowest  similarity among paraphrases    (SHOULD hit):     {min_paraphrase:.4f}")

    if max_adverse is not None and min_paraphrase is not None:
        gap = min_paraphrase - max_adverse
        if gap > 0:
            safe_threshold = (max_adverse + min_paraphrase) / 2
            print(f"\nSafe threshold suggestion: {safe_threshold:.4f}")
            print(f"  (gap between adverse ceiling and paraphrase floor: {gap:+.4f})")
        else:
            print("\n⚠  NO SAFE THRESHOLD EXISTS with this embedder on this test set.")
            print(f"   Adverse pairs reach higher similarity ({max_adverse:.4f})")
            print(f"   than genuine paraphrases ({min_paraphrase:.4f}).")
            print("   The cache cannot distinguish between the two categories using")
            print("   cosine similarity alone. Options:")
            print("     - Use a stronger Spanish-specialized embedder")
            print("     - Add symbolic checks (negation detection, entity NER)")
            print("     - Disable the cache for this corpus type")

    print("\n" + "=" * 70)
    print("Save this output. It's the evidence for the next article.")
    print("=" * 70)


if __name__ == "__main__":
    main()
