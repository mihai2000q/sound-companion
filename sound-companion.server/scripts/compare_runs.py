"""Compare two saved retrieval runs. Run from the server folder:
`uv run python -m scripts.compare_runs eval/results/<baseline>.json eval/results/<new>.json`.

Prints the change per question and overall (second run minus first) and the settings that differ,
so a change in precision can be tied to the change that caused it.
"""

import argparse
from pathlib import Path

from app.rag.eval_results import compare, load_run


def main(path_a: Path, path_b: Path) -> None:
    a, b = load_run(path_a), load_run(path_b)
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
    if result["settings"]:
        print("\nsettings that differ:")
        for key, (va, vb) in result["settings"].items():
            print(f"  {key}: {va} -> {vb}")
    else:
        print("\nsettings are the same")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("baseline", type=Path)
    parser.add_argument("new", type=Path)
    args = parser.parse_args()
    main(args.baseline, args.new)
