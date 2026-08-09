"""
Significancia -- test exacto de permutacion sobre AUC.

Por que existe
--------------
Los contrastes tienen n chico (5 vs 9, 2 vs 9). La objecion natural es
que un AUC de 0.9333 con 45 comparaciones puede salir por azar. Juntar
mas pares es una respuesta; calcular la probabilidad exacta es la otra,
y no requiere datos nuevos.

Bajo la hipotesis nula de que las etiquetas accept/reject no informan
nada sobre la similitud, cualquier reasignacion de etiquetas a los
mismos scores es igual de probable. Con n chico ese espacio se enumera
completo: C(14,5) = 2002 reasignaciones para el contraste principal.
No hay aproximacion normal ni supuesto distribucional. Es el p-valor
exacto.

CORRECCION respecto de la primera version de este script
---------------------------------------------------------
La primera version estimaba el intervalo del margen por bootstrap. Eso
estaba mal. El margen es min(accept) - max(reject), un estadistico de
valores extremos. Un remuestreo con reemplazo nunca produce un minimo
menor al minimo muestral ni un maximo mayor al maximo muestral, asi que
el margen remuestreado es SIEMPRE mayor o igual al observado. La
distribucion queda acotada por abajo por el propio valor observado, el
percentil 2.5 colapsa contra esa cota, y la fraccion de replicas con
margen positivo mide la asimetria de la cota, no los datos. En un
contraste con margen observado negativo esa fraccion llegaba a 54%,
que es un artefacto puro.

Se reemplaza por jackknife leave-one-out, que responde la pregunta que
de verdad importa para un punto de corte: depende este margen de una
sola observacion. Se recalcula el margen quitando un par a la vez y se
reporta el rango, el par mas influyente, y si algun retiro cambia el
signo.

Tres salidas por contraste
--------------------------
1. AUC con p-valor exacto y el p-valor MINIMO alcanzable dado el n. Ese
   piso importa: con n=2 vs n=9 el minimo p bilateral es ~0.036, asi que
   ningun resultado de ese contraste puede ser fuertemente significativo
   por construccion.

2. Tasa de error en el mejor punto de operacion. Usa todos los scores,
   no dos. Responde la pregunta operativa: con el mejor umbral posible
   para este contraste, cuantos pares se clasifican mal.

3. Jackknife del margen, con identificacion del par influyente.

Uso:
    python significance.py                    # lee resultados_v4.json
    python significance.py otro.json

No requiere Ollama. No recalcula embeddings.
"""

import argparse
import json
import random
import sys
from itertools import combinations
from typing import List, Dict, Any, Tuple

try:
    from analyze_contrasts import CONTRASTS
except ImportError:
    CONTRASTS = [
        ("confirmatory", "negation", "Both are negative-particle insertions."),
        ("paraphrase-high", "negation", "Overlap approximately matched."),
        ("paraphrase-high", "temporal", "Overlap approximately matched."),
        ("paraphrase-high", "entity", "Overlap approximately matched."),
        ("paraphrase-low", "negation", "UNMATCHED overlap."),
    ]

DEFAULT_JSON = "resultados_v4.json"

# Ver la nota en analyze_contrasts.py: solo afecta prosa y cabecera.
DEFAULT_METRIC_LABEL = "cosine similarity"

EXACT_LIMIT = 250000
MC_SAMPLES = 100000
SEED = 20260808

# Contraste preespecificado. Los demas son descriptivos.
PRIMARY = ("paraphrase-high", "negation")

SEP_HEAVY = "=" * 74
SEP_LIGHT = "-" * 74


def auc_from_split(accept: List[float], reject: List[float]) -> float:
    wins = 0.0
    for a in accept:
        for r in reject:
            if a > r:
                wins += 1.0
            elif a == r:
                wins += 0.5
    return wins / (len(accept) * len(reject))


def n_choose_k(n: int, k: int) -> int:
    result = 1
    for i in range(k):
        result = result * (n - i) // (i + 1)
    return result


def permutation_test(accept: List[float], reject: List[float]) -> Dict[str, Any]:
    observed = auc_from_split(accept, reject)
    pool = accept + reject
    n_total = len(pool)
    n_a = len(accept)
    space = n_choose_k(n_total, n_a)
    deviation = abs(observed - 0.5)
    extreme = 0
    total = 0

    if space <= EXACT_LIMIT:
        mode = "exact"
        indices = range(n_total)
        for combo in combinations(indices, n_a):
            chosen = set(combo)
            a = [pool[i] for i in indices if i in chosen]
            r = [pool[i] for i in indices if i not in chosen]
            if abs(auc_from_split(a, r) - 0.5) >= deviation - 1e-12:
                extreme += 1
            total += 1
    else:
        mode = f"monte-carlo n={MC_SAMPLES}"
        rng = random.Random(SEED)
        for _ in range(MC_SAMPLES):
            shuffled = pool[:]
            rng.shuffle(shuffled)
            if abs(auc_from_split(shuffled[:n_a], shuffled[n_a:]) - 0.5) >= deviation - 1e-12:
                extreme += 1
            total += 1

    return {
        "auc": observed,
        "p_value": extreme / total,
        "mode": mode,
        "space": space,
        "p_floor": 2.0 / space if space <= EXACT_LIMIT else 2.0 / MC_SAMPLES,
        "n_accept": n_a,
        "n_reject": len(reject),
    }


def best_operating_point(accept: List[float], reject: List[float]) -> Dict[str, Any]:
    """Umbral que minimiza errores totales. Usa todos los scores."""
    best = None
    for c in sorted(set(accept + reject)):
        for t in (c, c + 1e-9):
            false_hits = sum(1 for r in reject if r >= t)
            missed = sum(1 for a in accept if a < t)
            entry = {
                "threshold": t,
                "false_hits": false_hits,
                "missed_hits": missed,
                "errors": false_hits + missed,
            }
            if best is None or entry["errors"] < best["errors"]:
                best = entry
    total = len(accept) + len(reject)
    best["error_rate"] = best["errors"] / total
    best["n_total"] = total
    return best


def jackknife_margin(accept: List[Tuple[str, float]],
                     reject: List[Tuple[str, float]]) -> Dict[str, Any]:
    """
    Recalcula el margen quitando un par a la vez.

    Reemplaza al bootstrap, que degenera sobre estadisticos de valores
    extremos. El jackknife no estima un intervalo de confianza: mide
    dependencia de observaciones individuales, que es la pregunta
    relevante para un punto de corte.
    """
    a_scores = [s for _, s in accept]
    r_scores = [s for _, s in reject]
    observed = min(a_scores) - max(r_scores)

    replicates = []
    for i, (pid, _) in enumerate(accept):
        rest = a_scores[:i] + a_scores[i + 1:]
        if rest:
            replicates.append((min(rest) - max(r_scores), pid, "accept"))
    for i, (pid, _) in enumerate(reject):
        rest = r_scores[:i] + r_scores[i + 1:]
        if rest:
            replicates.append((min(a_scores) - max(rest), pid, "reject"))

    values = [v for v, _, _ in replicates]
    most_influential = max(replicates, key=lambda x: abs(x[0] - observed))
    sign_flips = [(v, pid, grp) for v, pid, grp in replicates
                  if (v > 0) != (observed > 0)]

    return {
        "observed": observed,
        "min": min(values),
        "max": max(values),
        "most_influential": most_influential,
        "influence": abs(most_influential[0] - observed),
        "sign_flips": sign_flips,
        "n_replicates": len(replicates),
    }


def scores_for(results: List[Dict[str, Any]], category: str) -> List[Tuple[str, float]]:
    return [(r["id"], r["similarity"]) for r in results if r["category"] == category]


def stars(p: float) -> str:
    if p < 0.01:
        return "  **"
    if p < 0.05:
        return "  *"
    return "  (not significant at 0.05)"


def report(results: List[Dict[str, Any]], accept_cat: str,
           reject_cat: str, note: str) -> None:
    accept = scores_for(results, accept_cat)
    reject = scores_for(results, reject_cat)

    is_primary = (accept_cat, reject_cat) == PRIMARY
    tag = "  [PRIMARY, pre-specified]" if is_primary else "  [descriptive]"

    print("")
    print(f"  {accept_cat} (accept) vs {reject_cat} (reject){tag}")
    print(f"    {note}")

    if len(accept) < 2 or len(reject) < 2:
        print("    -> not enough pairs in this scope.")
        return

    a_scores = [s for _, s in accept]
    r_scores = [s for _, s in reject]

    perm = permutation_test(a_scores, r_scores)
    print(f"    n = {perm['n_accept']} vs {perm['n_reject']}   "
          f"label assignments = {perm['space']}   [{perm['mode']}]")
    print(f"    AUC = {perm['auc']:.4f}   p = {perm['p_value']:.4f}"
          f"{stars(perm['p_value'])}")
    print(f"    lowest attainable p at this n: {perm['p_floor']:.4f}")
    if perm["p_value"] <= perm["p_floor"] + 1e-9:
        print("      -> p is AT the floor. The test cannot distinguish this")
        print("         result from any other extreme one. One bit of info.")
    elif perm["p_floor"] > 0.01:
        print("      -> this contrast cannot reach p < 0.01 by construction.")

    op = best_operating_point(a_scores, r_scores)
    if op["missed_hits"] == len(accept):
        print("    best operating point: degenerate -- rejects everything")
        print("      the error-minimising configuration is NO CACHE")
    else:
        print(f"    best operating point: threshold {op['threshold']:.4f}   "
              f"errors {op['errors']}/{op['n_total']} "
              f"(rate {op['error_rate']:.3f})")
        print(f"      false hits {op['false_hits']}   "
              f"legitimate hits lost {op['missed_hits']}/{len(accept)}")

    jk = jackknife_margin(accept, reject)
    print(f"    margin = {jk['observed']:+.4f}   "
          f"jackknife range [{jk['min']:+.4f}, {jk['max']:+.4f}]")
    _, pid, grp = jk["most_influential"]
    print(f"      most influential pair: {pid} ({grp}) -- "
          f"removing it moves the margin by {jk['influence']:.4f}")
    if jk["sign_flips"]:
        flipped = ", ".join(pid for _, pid, _ in jk["sign_flips"])
        print(f"      SIGN FLIPS on removing: {flipped}")
        print("         -> the sign of the margin is not robust to one pair.")
    else:
        print("      sign of margin is stable across all leave-one-out replicates.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Exact permutation test on AUC, with jackknife margins.")
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
    print("Significance -- exact permutation test on AUC")
    print(SEP_HEAVY)
    print(f"Source: {path}")
    print(f"Generated: {payload.get('generated_at', 'unknown')}")
    print(f"Metric:  {metric_label}")
    print("  Margins and thresholds below are in the units of this metric.")
    print("  AUC and p-values are not: they depend only on rank order, so")
    print("  they ARE comparable across metrics. Margins are NOT.")
    print("")
    print(f"H0: accept/reject labels carry no information about the score")
    print(f"    ({metric_label}).")
    print("Two-sided test on the deviation of AUC from 0.50.")
    print(f"Pre-specified primary contrast: {PRIMARY[0]} vs {PRIMARY[1]}.")
    print("All others are descriptive and are not corrected for multiplicity.")

    for scope, results in results_by_scope.items():
        print("")
        print(SEP_HEAVY)
        print(f"SCOPE: {scope}")
        print(SEP_HEAVY)
        for accept_cat, reject_cat, note in CONTRASTS:
            report(results, accept_cat, reject_cat, note)

    print("")
    print(SEP_HEAVY)
    print("HOW TO READ THIS")
    print(SEP_HEAVY)
    print("")
    print("  A significant AUC below 0.50 means the score is reliably")
    print("  INVERTED: adverse pairs rank above genuine paraphrases.")
    print("")
    print("  A non-significant AUC near 0.50 means the score carries no")
    print("  usable information for this contrast. That is the claim to")
    print("  make -- not that the model 'performs worse', which the")
    print("  data does not support.")
    print("")
    print("  An AUC near 1.00 with a negative or near-zero margin means")
    print("  the ordering is right but the cut point is not usable. A")
    print("  cache needs the cut point, not the ordering.")
    print("")
    print("  The jackknife is not a confidence interval. It answers one")
    print("  question: does this margin depend on a single observation.")
    print("")
    print(SEP_HEAVY)


if __name__ == "__main__":
    main()
