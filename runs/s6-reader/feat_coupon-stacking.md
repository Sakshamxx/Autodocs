# feat(coupons): allow stacking one percent and one flat coupon

This branch updates coupon service and pricing to allow up to two coupons per order—specifically one percent coupon and one flat coupon. Percent coupons are applied to the full subtotal first, and flat coupons apply to the remaining balance. Duplicate coupon kinds per cart are disallowed.

## Changes
- Increased MAX_COUPONS_PER_ORDER to 2 and added a check to prevent applying more than one coupon of the same kind.
- Introduced stack_discounts to sort applied coupons so percent coupons apply first, followed by flat coupons against the remainder.
- Updated quote_cart to use stacked discounts and added comprehensive tests for coupon stacking and redemption limits.

## Functions
- `shoplite/services/coupons.py::kind_already_applied` (implemented): Returns True if the cart already contains a coupon of the specified kind.
- `shoplite/services/coupons.py::apply_coupon` (implemented): Attaches a coupon to the user's cart after validating that the coupon is not already applied, the cart has not exceeded the maximum coupon limit, and the same coupon kind is not already present.
- `shoplite/services/pricing.py::quote_cart` (implemented): Calculates the pricing details for a cart including subtotal, stacked discounts, shipping rate, and final total.
- `shoplite/services/pricing.py::stack_discounts` (implemented): Applies percent coupons first to the full subtotal and then flat coupons to the remaining amount, returning a list of tuples containing each coupon and its calculated discount amount.

## Could not determine
- Nothing.

## Release note
Orders can now use two coupons: one percent and one flat. Percent coupons apply first.
