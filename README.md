# Material shortage recovery planner

A bicycle assembly line has enough pinch bolts for one more bike. The next shipment was due Wednesday. On Tuesday morning the supplier revises the arrival date and offers a rush delivery. The planner decides how much that offer is worth and which orders to release.

**Open `Material_Shortage_Planner.html` in a browser.** The report runs offline. Change the regular arrival day or the rush fee to compare two release plans. The Python model supports HiGHS and Gurobi. A standalone AIMMS version uses the same nine orders.

## A two-minute demo

1. Start with **Thursday delivery and a $350 rush fee**. Keeping Thursday costs $515 in late fees. Rushing would cost $225 in late fees plus $350 for freight. The most the planner would pay for the earlier shipment is $290.
2. Look at **#43800**. It is due Wednesday and costs $100 per workday late. The plan saves the last four bolts for that order. The customer behind #43719, whose penalty is $25 a day, waits until the following Monday.
3. Change the quote to **$250**. Wednesday delivery now costs $475 in total and seven of the nine orders can ship on time. At exactly $290, the planner keeps the regular shipment.

At the starting quote, the earliest-due rule pays for the rush and ships seven orders on time for $605. The recovery plan ships four on time for $515. If seven orders must ship on time, accept the rush and use the optimized release schedule. It reaches seven for $575, which is $60 above the lowest-cost plan. The late fees are one way to value a missed promise, and this comparison makes that judgment visible.

## How the plan works

On Monday, the line publishes a release schedule using the promised receipt date. It gives the next slot to the earliest due order with a complete kit. Monday’s two completed builds stay fixed when the supplier calls on Tuesday. Both policies see the same updated arrival and can buy the same rush option.

For each arrival, a binary variable selects the build day for each open order. Daily builds must fit the two-bike capacity. By the end of every day, total parts consumed must fit opening stock plus receipts to date. An order uses one frame of the right size and four bolts for its seat assembly. Other components are ready. Builds ship that day, and each day on the calendar is a workday.

The objective is the total fee for late orders. Among equally priced schedules, the model keeps as many published dates as possible, then favors earlier builds. Each policy compares its late fees with and without the rush. Buying the rush makes sense when the fee is below the difference. A tie goes to regular freight.

## Data

Microsoft’s AdventureWorks OLTP sample supplies nine order-line identifiers and quantities, three Road-150 frame sizes and the component quantities. The bolt requirement follows two BOM links, from bike to seat assembly (519) and from seat assembly to pinch bolt (497). The frame is issued as a complete subassembly. `extract.sql` shows the exact joins, selected order-line IDs and BOM snapshot date.

The public sample orders originally span several dates. This case groups them into one week. Due dates, fees, opening stock, shipment timing and line capacity are illustrative. The calculated dollar amounts apply to this case.

Source tables are available from [Microsoft AdventureWorks](https://learn.microsoft.com/en-us/sql/samples/adventureworks-install-configure), [product master](https://www.w3resource.com/sql-exercises/adventureworks/production/product.php), [bill of materials](https://www.w3resource.com/sql-exercises/adventureworks/production/billofmaterials.php), and [sales order lines](https://www.w3resource.com/sql-exercises/adventureworks/sales/salesorderdetail.php).

## Rebuild

Use Python 3.10 or later. Run these commands in the project directory.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python build_report.py
python -m unittest -v
```

`case.json` holds the small planning case. `planner.py` contains the due-date rule and the integer model, solved with SciPy and HiGHS. The report generator solves each supported arrival once. Changing the quote in the browser compares the resulting costs instantly.

The tests check material balances, daily capacity and Monday’s fixed releases. A separate exhaustive search checks the minimum late fees for all three arrival dates.

## Gurobi

To generate the same interactive report with Gurobi, run the following commands in the project’s Python environment.

```sh
python -m pip install -r requirements-gurobi.txt
python build_report.py --solver gurobi
python -m unittest -v
```

Gurobi first minimizes late fees, then changes to published dates, then the sum of the scheduled build days. It solves each delivery scenario with the same material and capacity limits as HiGHS. The comparison test checks those three objective values and verifies the resulting schedule. Equally good schedules can differ in individual release dates.

## AIMMS

Open **`aimms/ShortageRecovery.aimms`** in AIMMS Developer on Windows. Use CBC as the MIP solver. Run **MainExecution** from the Model Explorer. The data page for **LateFees** shows the three delivery scenarios. **ReleaseDay** gives each order’s build day, with Monday indexed as zero.

Set **RegularDelivery** and **RushQuote** in their data pages and rerun MainExecution to compare another offer. **BreakEvenFee**, **SelectedDelivery**, and **TotalCost** show the buying decision. The default is a Thursday arrival and a $350 quote.

| Bolt delivery | Reference minimum late fees |
| --- | ---: |
| Wednesday | $225 |
| Thursday | $515 |
| Friday | $885 |

The standalone model reads its own copy of the planning inputs from `aimms/case.dat`, including the schedule published on Monday. For the bundled case, run **CheckSample** to compare its three costs with the reference values. The Python test suite also checks that the AIMMS snapshot matches `case.json`.
