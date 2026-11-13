# fix(stock): prevent race conditions and release holds on payment failure immediately

This branch fixes a stock race condition by replacing separate read-and-write checks with a single conditional UPDATE statement. It also ensures that failed or gateway-timed-out payments release their reserved stock holds immediately rather than waiting for TTL expiration.

## Changes
- Replaced read-then-write stock reservation checks with a single atomic conditional UPDATE (`try_reserve`).
- Released stock holds immediately upon payment failure or gateway errors via `release_order_holds`.
- Updated tests to verify immediate stock release on failed payments and gateway errors.

## Functions
- `shoplite/services/checkout.py::record_failed_payment` (implemented): Marks the order as failed, immediately releases its stock holds, saves the payment attempt, and updates metrics.
- `shoplite/services/stock.py::try_reserve` (implemented): Attempts to reserve stock in a single conditional database update, returning True if successful.
- `shoplite/services/stock.py::reserve_for_order` (implemented): Reserves stock for each order line using try_reserve, raising OutOfStock if reservation fails.
- `shoplite/services/stock.py::release_order_holds` (implemented): Releases all active reservation entries for an order unless the reservation leak fault is enabled.

## Could not determine
- Nothing.

## Release note
Fixed checkout stock race conditions and made failed/timed-out payments release stock holds immediately.
