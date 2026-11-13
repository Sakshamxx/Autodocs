# feat(coupons): allow stacking one percent and one flat coupon

Updates coupon validation and pricing logic so a cart can hold up to two coupons as long as one is percentage-based and the other is flat. Percent coupons are applied to the full subtotal first, and flat coupons are applied to the remaining amount. Duplicate coupon kinds in the same cart are rejected.

## Changes
- Increased MAX_COUPONS_PER_ORDER from 1 to 2 with a rule allowing at most one percent and one flat coupon.
- Added kind_already_applied helper to check if a cart already contains a coupon of a specific kind.
- Added stack_discounts function in pricing to apply percent coupons first, then flat coupons to the remaining subtotal.
- Updated quote_cart to use stack_discounts for calculating cart coupon deductions.
- Added tests for coupon stacking, discount bounds, and redemption logging.

## Functions
- `shoplite/services/coupons.py::kind_already_applied` (implemented): Returns true if the cart already has an applied coupon matching the given kind.
- `shoplite/services/coupons.py::apply_coupon` (implemented): Attaches a coupon to the user's cart after ensuring it is not already applied, the coupon limit/kind constraints are respected, and it is redeemable.
- `shoplite/services/pricing.py::quote_cart` (implemented): Computes the subtotal, stacked discounts, shipping rate, and final total for the cart.
- `shoplite/services/pricing.py::stack_discounts` (implemented): Applies percent coupons first to the full subtotal and then flat coupons to the remaining balance.

## Could not determine
- Nothing.

## Release note
Orders can now use up to two coupons (one percent and one flat), with percent coupons applied first.
