# feat(coupons): allow stacking one percent and one flat coupon per order

This branch increases the maximum coupons per order from one to two, specifically allowing a cart to hold at most one percent coupon and one flat coupon. It implements discount stacking where percent coupons apply to the full subtotal first and flat coupons apply to the remaining balance. Validation and pricing logic are updated accordingly.

## Changes
- Increased MAX_COUPONS_PER_ORDER to 2 and added kind-based validation to ensure at most one percent and one flat coupon can be applied per order.
- Added kind_already_applied helper function in coupons service.
- Added stack_discounts pricing helper to sort and apply percent coupons before flat coupons.
- Updated cart quote logic to use stack_discounts.
- Added comprehensive test cases covering coupon stacking, discount limits, and redemption logging.

## Functions
- `shoplite/services/coupons.py::kind_already_applied` (implemented): Returns true if the cart already contains an applied coupon of the specified kind.
- `shoplite/services/coupons.py::apply_coupon` (implemented): Attaches a coupon to the user's cart after verifying it is not already applied, the coupon limit and kind restrictions are respected, and it is redeemable.
- `shoplite/services/pricing.py::quote_cart` (implemented): Computes the subtotal, stacked coupon discounts, shipping rate, and final total for the cart.
- `shoplite/services/pricing.py::stack_discounts` (implemented): Sorts applied coupons to apply percent coupons first and flat coupons to the remaining balance, returning a list of coupon discount tuples.

## Could not determine
- Nothing.

## Release note
Orders can now use up to two coupons: one percent coupon and one flat coupon. Percent coupons apply first.
