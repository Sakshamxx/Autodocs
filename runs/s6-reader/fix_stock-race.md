# fix(stock): prevent race conditions and release holds on failed payments

This branch replaces separate stock checks and updates with a single conditional UPDATE statement to prevent race conditions during checkout. It also ensures that failed or errored payments immediately release stock holds instead of waiting for expiration.

## Changes
- Replaced read-then-write stock reservation with a single conditional UPDATE using `try_reserve`.
- Released stock holds immediately when an order payment fails or encounters a gateway error.
- Updated tests to verify immediate stock release on failed/errored payments and updated metric assertions.

## Functions
- `shoplite/services/checkout.py::record_failed_payment` (implemented): Releases order stock holds, marks the order as payment failed, and records a failed payment attempt.
- `shoplite/services/stock.py::try_reserve` (implemented): Attempts to hold inventory units in a single conditional update statement, returning True if successful.
- `shoplite/services/stock.py::reserve_for_order` (implemented): Reserves stock for each line of an order using try_reserve and creates reservation entries.
- `shoplite/services/stock.py::release_order_holds` (implemented): Releases all active reservation entries for an order unless the reservation leak fault is enabled.

## Could not determine
- Nothing.

## Release note
Fixed stock race conditions during simultaneous checkouts and ensured failed payments release held stock immediately.
