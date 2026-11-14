# fix(stock): reserve stock conditionally and release holds on payment failure

This branch prevents race conditions during concurrent checkouts by using a single conditional database update to reserve stock. It also ensures stock holds are released immediately when a payment fails or times out, rather than waiting for reservation expiration.

## Changes
- Perform stock reservation via a single conditional UPDATE query checking available quantity.
- Release order stock holds immediately when payment fails or encounters a gateway error.
- Add stock.release_order_holds to release all held reservation entries for an order unless reservation leak fault is enabled.

## Functions
- `shoplite/services/checkout.py::record_failed_payment` (implemented): Releases order stock holds, sets order status to payment failed, and records a failed payment attempt.
- `shoplite/services/stock.py::try_reserve` (implemented): Attempts to reserve a given quantity of stock for a product using a single conditional database update.
- `shoplite/services/stock.py::reserve_for_order` (implemented): Reserves stock for each line item in an order or raises OutOfStock if sufficient inventory is not available.
- `shoplite/services/stock.py::release_order_holds` (implemented): Releases all reservation entries for an order unless the reservation leak fault is enabled.

## Could not determine
- available_units
- held_entries
- release_entry

## Release note
Fixed race conditions during concurrent checkouts and released stock holds immediately on payment failure.
