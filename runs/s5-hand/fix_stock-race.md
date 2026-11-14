# fix(stock): prevent race conditions and release holds on failed payments

Fixes a concurrency race condition in stock reservation by utilizing a conditional UPDATE statement. Also updates checkout so that failed or timed-out payments immediately release their stock holds rather than waiting for expiration.

## Changes
- Replaced separate stock read-and-write checks with a conditional update in `try_reserve` to prevent race conditions during concurrent checkouts.
- Called `release_order_holds` immediately inside `record_failed_payment` when a payment fails or times out.
- Updated tests to verify that failed payments release holds instantly and that concurrent reservations are safely handled.

## Functions
- `shoplite/services/checkout.py::record_failed_payment` (implemented): Mark the order failed, release its stock holds, and save the payment attempt.
- `shoplite/services/stock.py::try_reserve` (implemented): Hold units in one conditional UPDATE; returns False if there is not enough stock.
- `shoplite/services/stock.py::reserve_for_order` (implemented): Hold stock for every line of an order using try_reserve, or raise OutOfStock.
- `shoplite/services/stock.py::release_order_holds` (implemented): Give back all of an order's held stock unless the reservation leak fault is enabled.

## Could not determine
- Nothing.

## Release note
Two checkouts at the same moment can no longer both take the last unit thanks to a conditional update, and failed/timed-out payments now release their stock holds immediately.
