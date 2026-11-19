"""Build a self-contained report with a plan for each supplier arrival."""

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from planner import compare, load_case, recover


def build(directory, solve=recover):
    case, orders = load_case(directory / "case.json")
    published, scenarios = compare(case, orders, solve)
    data = {
        "case": case,
        "orders": [asdict(o) for o in orders],
        "published": [published[o.id] for o in orders],
        "scenarios": scenarios,
    }
    template = (directory / "report.html.in").read_text()
    # Escaping '<' keeps JSON strings inside the script element.
    report = template.replace("__CASE_DATA__", json.dumps(data).replace("<", r"\u003c"))
    regular, rush = scenarios[3]["model"], scenarios[case["shipment"]["rush"]]["model"]
    ceiling = regular["late"] - rush["late"]
    decision = "Take Wednesday's delivery" if 350 < ceiling else "Keep Thursday's delivery"
    note = (f"{decision}. Moving the bolts forward avoids ${ceiling:,} in late fees. "
            f"The supplier is asking $350.")
    report = report.replace("__STATIC_NOTE__", note)
    output = directory / "Material_Shortage_Planner.html"
    output.write_text(report, encoding="utf-8")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--solver", choices=("highs", "gurobi"), default="highs")
    args = parser.parse_args()
    solve = recover
    if args.solver == "gurobi":
        try:
            from gurobi_planner import recover as solve
        except ModuleNotFoundError as exc:
            if exc.name != "gurobipy":
                raise
            parser.exit(2, "Install the optional solver with: python -m pip install gurobipy\n")
    print(build(Path(__file__).resolve().parent, solve))
