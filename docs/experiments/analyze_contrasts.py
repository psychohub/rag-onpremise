"""
Reanalisis por contrastes -- controla el solapamiento lexico.

Por que existe
--------------
El AUC global de v4 compara TODOS los pares accept contra TODOS los
reject. Eso mezcla dos poblaciones de parafrasis muy distintas:

  paraphrase-low   query y twin comparten pocos tokens
  paraphrase-high  query y twin difieren en un solo token

Los pares de negacion difieren en un solo token. Compararlos contra
parafrasis de bajo solapamiento produce separacion aparente que puede
explicarse por forma superficial en vez de por semantica. Un revisor
razonable va a plantear exactamente esa objecion.

Este script computa AUC y margen para contrastes especificos, de modo
que cada afirmacion se pueda hacer con el solapamiento controlado.

El contraste decisivo es negation vs confirmatory:

  neg-01  "con dedicacion exclusiva" -> "sin dedicacion exclusiva"
          insercion de particula negativa. Debe RECHAZARSE.

  cnf-01  "Es obligatorio ...?" -> "No es obligatorio ...?"
          insercion de particula negativa. Debe ACEPTARSE.

Mismo tipo de cambio superficial, comportamiento requerido opuesto.
Si el puntaje no separa estas dos poblaciones, no queda explicacion
lexica, ni de idioma, ni de dominio: el embedder no representa el
alcance de la negacion.

Uso:
    python analyze_contrasts.py                      # lee resultados_v4.json
    python analyze_contrasts.py otro_archivo.json

No requiere Ollama. No recalcula embeddings.
"""

import argparse
import json
import sys
import statistics
from typing import List, Dict, Any, Optional, Tuple

DEFAULT_JSON = "resultados_v4.json"

# Nombre de la magnitud puntuada. Solo afecta la prosa del reporte y la
# cabecera: el computo es agnostico a la metrica porque AUC y margen se
# calculan sobre el campo "similarity" sea cual sea su escala. Existe
# para que un reporte generado sobre puntajes de reranker no afirme que
# se midio un coseno.
DEFAULT_METRIC_LABEL = "cosine similarity"

SEP_HEAVY = "=" * 74
SEP_LIGHT = "-" * 74

# (categoria_accept, categoria_reject, nota sobre el solapamiento)
CONTRASTS = [
    ("confirmatory", "negation",
     "DECISIVE. Both are negative-particle insertions. Overlap matched."),
    ("paraphrase-high", "negation",
     "Both differ by roughly one token. Overlap approximately matched."),
    ("paraphrase-high", "temporal",
     "Both differ by roughly one token."),
    ("paraphrase-high", "entity",
     "Both differ by roughly one token."),
    ("paraphrase-low", "negation",
     "UNMATCHED overlap. Any separation here may be surface form."),
]


def auc(accept: List[float], reject: List[float]) -> Optional[float]:
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


def scores_for(results: List[Dict[str, Any]], category: str) -> List[float]:
    return [r["similarity"] for r in results if r["category"] == category]


def describe(name: str, sims: List[float]) -> str:
    if not sims:
        return f"{name:17s} n=0"
    return (f"{name:17s} n={len(sims):<3d} "
            f"min={min(sims):.4f} max={max(sims):.4f} "
            f"mean={statistics.mean(sims):.4f}")


def report_contrast(results: List[Dict[str, Any]],
                    accept_cat: str, reject_cat: str, note: str) -> None:
    accept = scores_for(results, accept_cat)
    reject = scores_for(results, reject_cat)

    print("")
    print(f"  {accept_cat}  (accept)   vs   {reject_cat}  (reject)")
    print(f"    {note}")

    if not accept or not reject:
        print("    -> not available in this scope.")
        return

    print(f"    {describe(accept_cat, accept)}")
    print(f"    {describe(reject_cat, reject)}")

    a = auc(accept, reject)
    gap = min(accept) - max(reject)

    verdict = ""
    if a < 0.40:
        verdict = "  INVERTED"
    elif a < 0.60:
        verdict = "  no separability"
    elif a >= 0.99 and gap <= 0.02:
        verdict = "  ordered but margin under 0.02"

    print(f"    AUC = {a:.4f}{verdict}")
    print(f"    margin (min accept - max reject) = {gap:+.4f}", end="")
    if gap > 0:
        print(f"   threshold candidate: {(min(accept) + max(reject)) / 2:.4f}")
    else:
        print("   -> distributions overlap")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Contrast analysis with lexical overlap controlled.")
    parser.add_argument(
        "path", nargs="?", default=DEFAULT_JSON,
        help=f"JSON with the scores (default: {DEFAULT_JSON})")
    parser.add_argument(
        "--metric-label", default=DEFAULT_METRIC_LABEL,
        help="Name of the scored quantity, used in the report prose. "
             "Example: \"cross-encoder logit\". "
             f"Default: \"{DEFAULT_METRIC_LABEL}\".")
    args = parser.parse_args()
    path = args.path
    metric_label = args.metric_label

    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: no se encontro {path}")
        print("       Correr primero: python test_threshold_v4.py")
        sys.exit(1)

    results_by_scope = payload.get("results_by_scope", {})
    if not results_by_scope:
        print(f"ERROR: {path} no contiene results_by_scope")
        sys.exit(1)

    print(SEP_HEAVY)
    print("Contrast analysis -- lexical overlap controlled")
    print(SEP_HEAVY)
    print(f"Source: {path}")
    print(f"Generated: {payload.get('generated_at', 'unknown')}")
    print(f"Metric:  {metric_label}")
    print("  All scores, margins and threshold candidates below are in the")
    print("  units of this metric. They are not comparable across metrics.")

    decisive: Dict[str, Optional[float]] = {}

    for scope, results in results_by_scope.items():
        print("")
        print(SEP_HEAVY)
        print(f"SCOPE: {scope}")
        print(SEP_HEAVY)

        for accept_cat, reject_cat, note in CONTRASTS:
            report_contrast(results, accept_cat, reject_cat, note)

        acc = scores_for(results, "confirmatory")
        rej = scores_for(results, "negation")
        decisive[scope] = auc(acc, rej) if (acc and rej) else None

    print("")
    print(SEP_HEAVY)
    print("DECISIVE CONTRAST ACROSS SCOPES")
    print("confirmatory (accept) vs negation (reject)")
    print(SEP_HEAVY)
    print("")
    for scope, a in decisive.items():
        shown = "n/a" if a is None else f"{a:.4f}"
        print(f"  {scope:26s} AUC = {shown}")

    print("")
    print("  Both populations are single negative-particle insertions with")
    print("  opposite required cache behaviour. An AUC near 0.50 here means")
    print(f"  the score ({metric_label}) carries no information about whether")
    print("  a negation changes the answer -- which is the property a")
    print("  semantic cache depends on.")
    print("")
    print("  CAVEAT: confirmatory n=2 per scope. This contrast is the")
    print("  cleanest available but the smallest. Report the n alongside")
    print("  the AUC, always.")
    print("")
    print(SEP_HEAVY)


if __name__ == "__main__":
    main()
