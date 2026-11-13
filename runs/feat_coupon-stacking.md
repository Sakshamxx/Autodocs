# feat(coupons): allow stacking one percent and one flat coupon

This branch updates the cart and pricing services to allow up to two coupons per order (specifically one percent coupon and one flat coupon). Percent coupons are applied first to the full subtotal, and flat coupons are then applied to the remaining amount.

## Changes
- Increased maximum coupons per order from 1 to 2, ensuring at most one percent and one flat coupon can be applied.
- Added a helper function to check if a coupon kind is already applied to the cart.
- Added discount stacking logic in pricing service to compute percent discounts on the subtotal first and flat discounts on the remaining balance.
- Updated cart summary and tests to verify stacking behavior and validations.

## Functions
- `shoplite/services/coupons.py::kind_already_applied`: Returns True if the cart already contains an applied coupon of the specified kind.
- `shoplite/services/coupons.py::apply_coupon`: Attaches a coupon to the user's cart after validating uniqueness, coupon limits, kinds, and redeemability.
- `shoplite/services/pricing.py::quote_cart`: Computes the subtotal, stacked discounts, shipping, and total for a cart and returns a PriceQuote.
- `shoplite/services/pricing.py::stack_discounts`: Applies percent coupons first to the subtotal, then flat coupons to the remaining balance, returning a list of coupon-discount tuples.

## Could not determine
- Nothing.

## Release note
Orders can now use up to two coupons (one percent and one flat), with percent coupons applied first.
