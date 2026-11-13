# refactor(reports): split reports module into reports package

Refactored the monolithic reports service module into a structured package separated by business area (sales and stock). Created a reports package init exposing the report functions and split the implementation into separate files.

## Changes
- Moved shoplite/services/reports.py to shoplite/services/reports/sales.py
- Created shoplite/services/reports/stock.py containing low_stock report
- Created shoplite/services/reports/__init__.py to re-export report functions

## Functions
- `shoplite/services/reports/sales.py::sales_summary` (implemented): Calculates orders, revenue, discounts, and average order value between two dates.
- `shoplite/services/reports/sales.py::top_products` (implemented): Retrieves best-selling products by units sold between two dates up to a given limit.
- `shoplite/services/reports/stock.py::low_stock` (file does not parse): Active products with sellable stock at or below the threshold.

## Could not determine
- shoplite/services/reports/stock.py
- shoplite/services/reports/stock.py does not parse, so its functions could not be read

## Release note
No user-visible change.
