# feat(coupons): allow stacking one percent and one flat coupon

Orders can now apply up to two coupons concurrently, provided one is a percentage coupon and one is a flat coupon. Percent coupons are applied to the subtotal first, and flat coupons apply to the remainder.

## Changes
- Increased MAX_COUPONS_PER_ORDER from 1 to 2.
- Added kind_already_applied to prevent applying multiple coupons of the same kind to a cart.
- Added stack_discounts to apply percent coupons first and flat coupons to the remaining subtotal.
- Updated pricing quote calculation to use stacked discounts.
- Added and updated coupon stacking tests.

## Functions
- `shoplite/services/coupons.py::kind_already_applied` (implemented): Returns true if the cart already contains a coupon of the specified kind.
- `shoplite/services/coupons.py::apply_coupon` (implemented): Attaches a validated coupon to the user's cart ensuring max coupon limits and distinct kinds are respected.
- `shoplite/services/pricing.py::quote_cart` (implemented): Computes the price quote for the cart including stacked discounts and shipping.
- `shoplite/services/pricing.py::stack_discounts` (implemented): Applies percent coupons first to the subtotal and then flat coupons to the remaining amount.

## Could not determine
- Nothing.

## Release note
Orders can use two coupons: one percent and one flat. Percent coupons apply first.
