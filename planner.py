"""Release whole orders against available parts and daily assembly capacity."""

from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp


@dataclass(frozen=True)
class Order:
    id: int
    size: int
    qty: int
    due: int
    late_fee: int
    parts: dict[str, int]

    def penalty(self, day):
        return max(day - self.due, 0) * self.late_fee


def load_case(path):
    case = json.loads(Path(path).read_text())
    orders = []
    for row in case["orders"]:
        model = case["models"][row["model"]]
        qty = row["qty"]
        parts = {"PB-6109": model["bolts"] * qty, model["frame"]: model["frames"] * qty}
        orders.append(Order(row["id"], model["size"], qty, row["due"], row["late_fee"], parts))
    return case, sorted(orders, key=lambda order: (order.due, order.id))


def stock_by_day(case, arrival):
    stock = case["opening"].copy()
    receipts = [*case["receipts"], {**case["shipment"], "day": arrival}]
    supply = []
    for day in range(len(case["days"])):
        for receipt in receipts:
            if receipt["day"] == day:
                stock[receipt["part"]] += receipt["qty"]
        supply.append(stock.copy())
    return supply


def due_date_plan(case, orders, supply, start=0, released=None):
    plan = dict(released or {})
    used = dict.fromkeys(case["opening"], 0)
    for order in orders:
        if order.id in plan:
            for part, qty in order.parts.items():
                used[part] += qty
    for day in range(start, len(supply)):
        space = case["capacity"]
        for order in orders:
            if order.id in plan or order.qty > space:
                continue
            if any(used[p] + q > supply[day][p] for p, q in order.parts.items()):
                continue
            plan[order.id] = day
            space -= order.qty
            for part, qty in order.parts.items():
                used[part] += qty
    if len(plan) != len(orders):
        raise ValueError("Some orders do not fit. Check receipts, capacity and the planning horizon.")
    return plan


def recover(case, orders, supply, published, start=1):
    """Pick one build day per open order. Released orders have already consumed their kits."""
    released = {o.id: published[o.id] for o in orders if published[o.id] < start}
    pending = [o for o in orders if o.id not in released]
    if not pending:
        return released
    days = np.arange(start, len(supply))
    shape = (len(pending), len(days))
    rows, lower, upper = [], [], []

    def constraint(weights, low, high):
        rows.append(weights.ravel())
        lower.append(low)
        upper.append(high)

    for i in range(len(pending)):
        weights = np.zeros(shape)
        weights[i, :] = 1
        constraint(weights, 1, 1)

    for j, day in enumerate(days):
        slots = np.zeros(shape)
        slots[:, j] = [o.qty for o in pending]
        constraint(slots, 0, case["capacity"])
        for part, available in supply[day].items():
            spent = sum(o.parts.get(part, 0) for o in orders if o.id in released)
            usage = np.zeros(shape)
            usage[:, :j + 1] = [[o.parts.get(part, 0)] for o in pending]
            constraint(usage, 0, available - spent)

    # One dollar outweighs every tie-break. Then keep published dates, then finish early.
    max_day_sum = len(pending) * len(supply)
    change_weight = max_day_sum + 1
    dollar_weight = (len(pending) + 1) * change_weight
    cost = np.array([[o.penalty(day) * dollar_weight
                      + int(day != published[o.id]) * change_weight + day
                      for day in days] for o in pending])
    answer = milp(cost.ravel(), integrality=np.ones(cost.size),
                  bounds=Bounds(0, 1), constraints=LinearConstraint(rows, lower, upper),
                  options={"mip_rel_gap": 0.0})
    if not answer.success:
        raise ValueError(f"No optimal release plan available. {answer.message}")
    selected = answer.x.reshape(shape).argmax(axis=1)
    return {**released, **{o.id: int(days[j]) for o, j in zip(pending, selected)}}


def metrics(orders, plan, published):
    return {
        "days": [plan[o.id] for o in orders],
        "late": sum(o.penalty(plan[o.id]) for o in orders),
        "onTime": sum(plan[o.id] <= o.due for o in orders),
        "changed": sum(plan[o.id] != published[o.id] for o in orders),
    }


def compare(case, orders, solve=recover):
    shipment = case["shipment"]
    published = due_date_plan(case, orders, stock_by_day(case, shipment["promised"]))
    released = {key: day for key, day in published.items() if day == 0}
    scenarios = {}
    for arrival in shipment["regular_days"]:
        supply = stock_by_day(case, arrival)
        normal = due_date_plan(case, orders, supply, start=1, released=released)
        optimized = solve(case, orders, supply, published)
        scenarios[arrival] = {"rule": metrics(orders, normal, published),
                              "model": metrics(orders, optimized, published)}
    return published, scenarios
