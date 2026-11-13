# feat(coupons): allow stacking one percent and one flat coupon

This branch updates the coupon system to allow up to two coupons per order, provided they are of different kinds (one percent and one flat). Percent coupons are applied to the full subtotal first, and flat coupons are then applied to the remaining amount. New helper functions validate coupon kinds and compute stacked discounts.

## Changes
- Increased MAX_COUPONS_PER_ORDER from 1 to 2 with kind-based restrictions
- Added kind_already_applied helper to prevent duplicate coupon kinds in a cart
- Added stack_discounts to apply percent coupons before flat coupons sequentially
- Updated quote_cart to use stacked discounts
- Added and updated test cases for coupon stacking and validation

## Functions
- `shoplite/services/coupons.py::kind_already_applied` (implemented): True if the cart already has a coupon of this kind.
- `shoplite/services/coupons.py::apply_coupon` (implemented): Attach a coupon to the user's cart after checking it.
- `shoplite/services/pricing.py::quote_cart` (implemented): Work out what this cart costs right now.
- `shoplite/services/pricing.py::stack_discounts` (implemented): Apply percent coupons first, then flat ones to what is left.

## Could not determine
- Nothing.

## Release note
Orders can use two coupons: one percent and one flat. Percent coupons apply first.
