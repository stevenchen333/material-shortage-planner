"""Gurobi implementation of the daily release decision."""

import gurobipy as gp
from gurobipy import GRB


def recover(case, orders, supply, published, start=1):
    completed = {o.id: published[o.id] for o in orders if published[o.id] < start}
    pending = [o for o in orders if o.id not in completed]
    if not pending:
        return completed

    days = range(start, len(supply))
    with gp.Model("road_150_recovery") as model:
        model.Params.OutputFlag = 0
        model.Params.MIPGap = 0
        model.Params.MIPGapAbs = 0
        build = model.addVars([o.id for o in pending], days, vtype=GRB.BINARY, name="build")

        for order in pending:
            model.addConstr(build.sum(order.id, "*") == 1, name=f"assign_{order.id}")
        for day in days:
            load = gp.quicksum(o.qty * build[o.id, day] for o in pending)
            model.addConstr(load <= case["capacity"], name=f"capacity_{day}")

        for part in case["opening"]:
            spent = sum(o.parts.get(part, 0) for o in orders if o.id in completed)
            cumulative = gp.LinExpr()
            for day in days:
                cumulative += gp.quicksum(o.parts.get(part, 0) * build[o.id, day] for o in pending)
                model.addConstr(cumulative <= supply[day][part] - spent, name=f"stock_{part}_{day}")

        late_fees = gp.quicksum(o.penalty(d) * build[o.id, d] for o in pending for d in days)
        moves = gp.quicksum(1 - build[o.id, published[o.id]] for o in pending)
        build_days = gp.quicksum(d * build[o.id, d] for o in pending for d in days)
        objectives = [(late_fees, "late_fees"), (moves, "changes"), (build_days, "days")]
        for index, (expr, name) in enumerate(objectives):
            model.setObjectiveN(expr, index=index, priority=3 - index, abstol=0, reltol=0, name=name)

        model.optimize()
        if model.Status != GRB.OPTIMAL:
            raise ValueError(f"Gurobi did not find an optimal release schedule (status {model.Status}).")
        return {**completed, **{o.id: d for o in pending for d in days if build[o.id, d].X > 0.5}}
