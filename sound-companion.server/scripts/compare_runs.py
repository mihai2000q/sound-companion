"""Compare two saved runs, retrieval, tool-calling, injection or RAGAs. Run from the server folder:
`uv run python -m scripts.compare_runs eval/results/<baseline>.json eval/results/<new>.json`.

Prints the change per question and overall (second run minus first) and the settings that differ,
so a change in precision can be tied to the change that caused it.
"""

import argparse
from pathlib import Path

from app.agent import injection_eval
from app.agent.tool_eval import KIND
from app.agent.tool_eval import compare as compare_tools
from app.rag.eval_results import compare, differing_settings, group_means, load_run
from app.rag.evaluation import load_golden_set
from eval import run_ragas

GOLDEN_SET = Path(__file__).resolve().parents[2] / "data" / "golden-set.json"
EXACT_CATEGORIES = ("exact-term", "alias")


def pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def print_settings(changes: dict) -> None:
    if not changes:
        print("\nsettings are the same")
        return
    print("\nsettings that differ:")
    for key, (va, vb) in changes.items():
        print(f"  {key}: {va} -> {vb}")


def main_tools(a: dict, b: dict) -> None:
    result = compare_tools(a, b)
    print(f"A: {a['label']} ({a['date']})   B: {b['label']} ({b['date']})\n")
    print(f"{'':10} {'selection':>17} {'parameters':>17}")
    for sa, sb in result["summary"]:
        if sb is None:
            continue
        print(f"{sa['group']:10} {pct(sa['selection']):>7} -> {pct(sb['selection']):>5} "
              f"{pct(sa['parameter']):>9} -> {pct(sb['parameter']):>5}")
    for row in result["changed"]:
        (sel_a, sel_b), (par_a, par_b) = row["selection"], row["parameters"]
        print(f"{row['id']:5} selection {sel_a} -> {sel_b}, parameters {par_a} -> {par_b}")
    if not result["changed"]:
        print("no case changed")
    for side, ids in (("only in A", result["only_in_a"]), ("only in B", result["only_in_b"])):
        if ids:
            print(f"{side}: {', '.join(ids)}")
    print_settings(result["settings"])


def main_injection(a: dict, b: dict) -> None:
    result = injection_eval.compare(a, b)
    print(f"A: {a['label']} ({a['date']})   B: {b['label']} ({b['date']})\n")
    print(f"passed {result['summary'][0]['passed']}/{result['summary'][0]['cases']} -> {result['summary'][1]['passed']}/{result['summary'][1]['cases']}")
    for case_id, before, after in result["changed"]:
        print(f"{case_id:5} {'pass' if before else 'FAIL'} -> {'pass' if after else 'FAIL'}")
    if not result["changed"]:
        print("no case changed")
    print_settings(differing_settings(a, b))


def main_ragas(a: dict, b: dict) -> None:
    result = run_ragas.compare(a, b)
    print(f"A: {a['label']} ({a['date']})   B: {b['label']} ({b['date']})\n")
    for metric, (sa, sb) in result["summary"].items():
        mean_a, mean_b = sa["mean"], sb["mean"]
        delta = "" if mean_a is None or mean_b is None else f" ({mean_b - mean_a:+.3f})"
        print(f"{metric:18} {pct(mean_a):>5} (n={sa['questions']}) -> {pct(mean_b):>5} (n={sb['questions']}){delta}")
    for row in result["changed"]:
        print(f"{row['id']:5} " + ", ".join(f"{m} {pct(x)} -> {pct(y)}" for m, (x, y) in row["moves"].items()))
    if not result["changed"]:
        print("no score changed")
    for side, ids in (("only in A", result["only_in_a"]), ("only in B", result["only_in_b"])):
        if ids:
            print(f"{side}: {', '.join(ids)}")
    print_settings(differing_settings(a, b))


def main(path_a: Path, path_b: Path) -> None:
    a, b = load_run(path_a), load_run(path_b)
    if a.get("kind") != b.get("kind"):
        raise SystemExit("These are not the same kind of run (retrieval and tool-calling cannot be compared).")
    if a.get("kind") == KIND:
        return main_tools(a, b)
    if a.get("kind") == run_ragas.KIND:
        return main_ragas(a, b)
    if a.get("kind") == injection_eval.KIND:
        return main_injection(a, b)
    result = compare(a, b)
    print(f"A: {a['label']} ({a['date']})   B: {b['label']} ({b['date']})\n")
    print(f"{'id':5} {'P@' + str(a['settings']['k']):>13} {'':>8} {'R@' + str(a['settings']['k']):>13}")
    for row in result["questions"]:
        (pa, pb), (ra, rb) = row["precision"], row["recall"]
        print(f"{row['id']:5} {pa:5.2f} -> {pb:4.2f} {row['precision_change']:+6.2f}   {ra:5.2f} -> {rb:4.2f} {row['recall_change']:+6.2f}")
    sa, sb = a["summary"], b["summary"]
    print(f"\noverall precision {sa['precision']:.3f} -> {sb['precision']:.3f} ({result['precision_change']:+.3f}), "
          f"recall {sa['recall']:.3f} -> {sb['recall']:.3f} ({result['recall_change']:+.3f})")
    exact = {q.id for q in load_golden_set(GOLDEN_SET) if q.category in EXACT_CATEGORIES}
    groups_a, groups_b = group_means(a, {"exact-term and alias": exact}), group_means(b, {"exact-term and alias": exact})
    for name in groups_a.keys() & groups_b.keys():  # the groups of the current golden set
        (n, pa, ra), (_, pb, rb) = groups_a[name], groups_b[name]
        print(f"{name} ({n} questions): precision {pa:.3f} -> {pb:.3f} ({pb - pa:+.3f}), "
              f"recall {ra:.3f} -> {rb:.3f} ({rb - ra:+.3f})")
    for side, ids in (("only in A", result["only_in_a"]), ("only in B", result["only_in_b"])):
        if ids:
            print(f"{side}: {', '.join(ids)}")
    print_settings(result["settings"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("baseline", type=Path)
    parser.add_argument("new", type=Path)
    args = parser.parse_args()
    main(args.baseline, args.new)
