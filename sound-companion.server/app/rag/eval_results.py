"""Saving and comparing retrieval runs, so a later story can check a change against the baseline.

A run is one JSON file in `eval/results/`: a label, the date, the settings it ran with and the
per-question and overall metrics. Compare two files with `scripts.compare_runs`."""

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from app.rag.evaluation import QuestionResult, Summary

RESULTS_DIR = Path(__file__).resolve().parents[2] / "eval" / "results"


def build_run(
    label: str,
    settings: dict,
    summary: Summary,
    results: list[QuestionResult],
    filters: dict[str, dict],
    when: date | None = None,
) -> dict:
    """The record to save. `filters` maps a question id to a readable description of its filter."""
    return {
        "label": label,
        "date": (when or date.today()).isoformat(),
        "settings": settings,
        "summary": asdict(summary),
        "questions": [asdict(r) | {"filter": filters.get(r.id)} for r in results],
    }


def run_path(run: dict, directory: Path = RESULTS_DIR) -> Path:
    return directory / f"{run['date']}-{run['label']}.json"


def save_run(run: dict, directory: Path = RESULTS_DIR) -> Path:
    """Write the run. A saved run is never overwritten: pick a new label instead."""
    path = run_path(run, directory)
    if path.exists():
        raise FileExistsError(f"{path.name} already exists, use another label")
    directory.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(run, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_run(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _flatten(value, prefix: str = "") -> dict[str, object]:
    if isinstance(value, dict):
        return {k: v for key, item in value.items() for k, v in _flatten(item, f"{prefix}{key}.").items()}
    return {prefix.rstrip("."): value}


def differing_settings(a: dict, b: dict) -> dict[str, tuple[object, object]]:
    """Settings that are not the same in both runs, as `name: (in a, in b)`."""
    flat_a, flat_b = _flatten(a["settings"]), _flatten(b["settings"])
    return {
        key: (flat_a.get(key), flat_b.get(key))
        for key in sorted(flat_a.keys() | flat_b.keys())
        if flat_a.get(key) != flat_b.get(key)
    }


def compare(a: dict, b: dict) -> dict:
    """Per-question and overall change from run `a` to run `b` (b minus a)."""
    in_b = {q["id"]: q for q in b["questions"]}
    rows = []
    for q in a["questions"]:
        other = in_b.get(q["id"])
        if other is None:
            continue
        rows.append({
            "id": q["id"],
            "precision": (q["precision"], other["precision"]),
            "recall": (q["recall"], other["recall"]),
            "precision_change": other["precision"] - q["precision"],
            "recall_change": other["recall"] - q["recall"],
        })
    return {
        "questions": rows,
        "only_in_a": [q["id"] for q in a["questions"] if q["id"] not in in_b],
        "only_in_b": [i for i in in_b if i not in {q["id"] for q in a["questions"]}],
        "precision_change": b["summary"]["precision"] - a["summary"]["precision"],
        "recall_change": b["summary"]["recall"] - a["summary"]["recall"],
        "settings": differing_settings(a, b),
    }
