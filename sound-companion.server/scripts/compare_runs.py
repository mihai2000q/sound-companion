"""Compare two saved runs, retrieval or tool-calling. Run from the server folder:
`uv run python -m scripts.compare_runs eval/results/<baseline>.json eval/results/<new>.json`.

Prints the change per question and overall (second run minus first) and the settings that differ,
so a change in precision can be tied to the change that caused it.
"""

import argparse
from pathlib import Path

from app.agent.tool_eval import KIND, compare as compare_tools
from app.rag.eval_results import compare, load_run


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


def main(path_a: Path, path_b: Path) -> None:
    a, b = load_run(path_a), load_run(path_b)
    if a.get("kind") != b.get("kind"):
        raise SystemExit("These are not the same kind of run (retrieval and tool-calling cannot be compared).")
    if a.get("kind") == KIND:
        return main_tools(a, b)
    result = compare(a, b)
    print(f"A: {a['label']} ({a['date']})   B: {b['label']} ({b['date']})\n")
    print(f"{'id':5} {'P@' + str(a['settings']['k']):>13} {'':>8} {'R@' + str(a['settings']['k']):>13}")
    for row in result["questions"]:
        (pa, pb), (ra, rb) = row["precision"], row["recall"]
        print(f"{row['id']:5} {pa:5.2f} -> {pb:4.2f} {row['precision_change']:+6.2f}   {ra:5.2f} -> {rb:4.2f} {row['recall_change']:+6.2f}")
    sa, sb = a["summary"], b["summary"]
    print(f"\noverall precision {sa['precision']:.3f} -> {sb['precision']:.3f} ({result['precision_change']:+.3f}), "
          f"recall {sa['recall']:.3f} -> {sb['recall']:.3f} ({result['recall_change']:+.3f})")
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
