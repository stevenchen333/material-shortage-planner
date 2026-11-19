from importlib.util import find_spec
from pathlib import Path
import re
import unittest
from xml.etree import ElementTree

from planner import compare, due_date_plan, load_case, stock_by_day


ROOT = Path(__file__).resolve().parent


class AimmsCaseTest(unittest.TestCase):
    def test_snapshot_matches_python_case(self):
        case, orders = load_case(ROOT / "case.json")
        shipment = case["shipment"]
        published = due_date_plan(case, orders, stock_by_day(case, shipment["promised"]))
        data = (ROOT / "aimms/case.dat").read_text()
        tables = re.findall(r"COMPOSITE TABLE\n(.*?);", data, flags=re.S)
        datasets = {}
        for table in tables:
            header, *rows = [line.split() for line in table.strip().splitlines()]
            datasets[header[0]] = {row[0]: dict(zip(header[1:], row[1:], strict=True)) for row in rows}

        self.assertEqual(set(datasets['o']), {f'O{o.id}' for o in orders})
        scalars = dict(re.findall(r'^(\w+) := (\d+);', data, flags=re.M))
        self.assertEqual(int(scalars['DailyCapacity']), case['capacity'])
        self.assertEqual(int(scalars['ShipmentSize']), shipment['qty'])
        receipt, = case['receipts']
        self.assertEqual(receipt, {'part': 'FR-R92R-62', 'qty': int(scalars['FrameReceiptQty']),
                                   'day': int(scalars['FrameReceiptDay'])})
        for order in orders:
            row = datasets['o'][f'O{order.id}']
            self.assertEqual((int(row['BikeQty']), int(row['DueDay']), int(row['FeePerDay']),
                              int(row['PublishedDay']), row['BikeFrame']),
                             (order.qty, order.due, order.late_fee, published[order.id], f'Frame{order.size}'))
            self.assertEqual(order.parts['PB-6109'], order.qty * int(scalars['BoltsPerBike']))
            self.assertEqual(order.parts[f'FR-R92R-{order.size}'], order.qty)
        for part, qty in case['opening'].items():
            name = 'Bolt' if part == 'PB-6109' else 'Frame' + part.split('-')[-1]
            self.assertEqual(int(datasets['p'][name]['OpeningStock']), qty)
        scenario_days = {name: int(row['ArrivalDay']) for name, row in datasets['s'].items()}
        self.assertEqual(list(scenario_days.values()), shipment['regular_days'])
        self.assertEqual(scenario_days['Wednesday'], shipment['rush'])

    def test_project_references_the_supplied_model(self):
        project = ROOT / "aimms"
        main = ElementTree.parse(project / "ShortageRecovery.aimms").find("MainProject")
        folder = project / main.attrib["Path"]
        model = ElementTree.parse(folder / "Project.xml").findtext("ModelFileName")
        self.assertTrue((folder / model).is_file())


@unittest.skipUnless(find_spec("gurobipy"), "Optional gurobipy package is not installed")
class GurobiParityTest(unittest.TestCase):
    def test_release_dates_and_objectives(self):
        from gurobi_planner import recover

        case, orders = load_case(ROOT / "case.json")
        published, reference = compare(case, orders)
        _, gurobi = compare(case, orders, recover)
        for arrival in reference:
            with self.subTest(arrival=arrival):
                result = gurobi[arrival]["model"]
                target = reference[arrival]["model"]
                self.assertEqual((result['late'], result['changed'], sum(result['days'])),
                                 (target['late'], target['changed'], sum(target['days'])))
                builds = list(zip(orders, result['days'], strict=True))
                for order, day in builds:
                    self.assertEqual(day == 0, published[order.id] == 0)
                for day, stock in enumerate(stock_by_day(case, arrival)):
                    self.assertLessEqual(sum(o.qty for o, d in builds if d == day), case['capacity'])
                    for part, available in stock.items():
                        self.assertLessEqual(sum(o.parts.get(part, 0) for o, d in builds if d <= day), available)
