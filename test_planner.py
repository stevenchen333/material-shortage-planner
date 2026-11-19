import unittest
from pathlib import Path

from planner import compare, load_case, stock_by_day


class RecoveryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case, cls.orders = load_case(Path(__file__).with_name("case.json"))
        cls.published, cls.scenarios = compare(cls.case, cls.orders)

    def test_every_release_has_a_kit_and_a_slot(self):
        for arrival, policies in self.scenarios.items():
            supply = stock_by_day(self.case, arrival)
            for policy, result in policies.items():
                with self.subTest(arrival=arrival, policy=policy):
                    builds = list(zip(self.orders, result["days"], strict=True))
                    for order, day in builds:
                        self.assertIn(day, range(len(supply)))
                        self.assertEqual(day == 0, self.published[order.id] == 0)
                    for day, stock in enumerate(supply):
                        self.assertLessEqual(sum(o.qty for o, d in builds if d == day),
                                             self.case["capacity"])
                        for part, available in stock.items():
                            used = sum(o.parts.get(part, 0) for o, d in builds if d <= day)
                            self.assertLessEqual(used, available)

    def test_minimum_penalty_matches_exhaustive_search(self):
        for arrival, policies in self.scenarios.items():
            with self.subTest(arrival=arrival):
                supply = stock_by_day(self.case, arrival)
                open_orders = [o for o in self.orders if self.published[o.id] > 0]
                for order in self.orders:
                    if self.published[order.id] == 0:
                        for stock in supply:
                            for part, qty in order.parts.items():
                                stock[part] -= qty
                slots = [self.case["capacity"]] * len(supply)
                best = policies["rule"]["late"]

                def assign(index, cost):
                    nonlocal best
                    if cost >= best:
                        return
                    if index == len(open_orders):
                        best = cost
                        return
                    order = open_orders[index]
                    for day in range(1, len(slots)):
                        future = supply[day:]
                        if slots[day] < order.qty:
                            continue
                        if any(s[p] < q for s in future for p, q in order.parts.items()):
                            continue
                        slots[day] -= order.qty
                        for stock in future:
                            for part, qty in order.parts.items():
                                stock[part] -= qty
                        assign(index + 1, cost + order.penalty(day))
                        slots[day] += order.qty
                        for stock in future:
                            for part, qty in order.parts.items():
                                stock[part] += qty

                assign(0, 0)
                self.assertEqual(policies["model"]["late"], best)

    def test_thursday_quote(self):
        early = self.scenarios[2]["model"]
        regular = self.scenarios[3]["model"]
        self.assertEqual(regular["late"] - early["late"], 290)
        self.assertEqual((regular["late"], regular["onTime"]), (515, 4))
        self.assertEqual(self.scenarios[2]["rule"]["late"] + 350, 605)


if __name__ == "__main__":
    unittest.main()
