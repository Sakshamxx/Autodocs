# fix(stock): prevent race conditions and release holds on failed payments

This branch fixes a stock race condition by replacing the separate check-and-update steps with a single conditional UPDATE statement. It also ensures that failed or timed-out payments immediately release their stock holds rather than waiting for them to expire.

## Changes
- Replaced separate read and write inventory checks with a single conditional UPDATE via try_reserve to prevent race conditions during concurrent checkouts.
- Added release_order_holds to instantly release stock holds when an order payment fails or experiences a gateway error.
- Updated existing tests and metrics expectations to reflect immediate stock release on failed payments.

## Functions
- `shoplite/services/checkout.py::record_failed_payment` (implemented): Mark the order failed and save the payment attempt.
- `shoplite/services/stock.py::try_reserve` (implemented): Hold units in one conditional UPDATE; False if there is not enough stock.
- `shoplite/services/stock.py::reserve_for_order` (implemented): Hold stock for every line of an order, or raise OutOfStock.
- `shoplite/services/stock.py::release_order_holds` (implemented): Give back all of an order's held stock (skipped under the leak fault).

## Could not determine
- Nothing.

## Release note
Fixed stock race conditions during high concurrency and made failed payments release stock holds immediately instead of waiting for TTL expiration.
