# feat(coupons): allow stacking one percent and one flat coupon

Allows orders to accept up to two coupons per cart, requiring one percent coupon and one flat coupon. When calculating pricing quotes, percentage discounts are applied first against the full subtotal before flat discounts are applied to the remaining balance.

## Changes
- Allow stacking up to two coupons on an order provided one is a percentage coupon and one is a flat coupon.
- Apply percentage coupon discounts first to the full subtotal before applying flat coupon discounts to the remaining balance.

## Functions
- `shoplite/services/coupons.py::kind_already_applied` (implemented): Returns True if any coupon currently applied to the cart shares the given coupon kind.
- `shoplite/services/coupons.py::apply_coupon` (implemented): Attaches a coupon to a user's cart after validating that the coupon is not already applied, the cart has fewer than two coupons, and no coupon of the same kind is already applied.
- `shoplite/services/pricing.py::quote_cart` (implemented): Calculates total costs for a cart by computing stacked coupon discounts and adding shipping rates to the net subtotal.
- `shoplite/services/pricing.py::stack_discounts` (implemented): Orders cart coupons so percentage coupons apply first to the subtotal and flat coupons apply to the remaining subtotal.

## Could not determine
- cart_subtotal
- check_redeemable
- clock.utcnow
- get_cart
- get_coupon
- shipping.shipping_rate_for

## Release note
Orders can use two coupons: one percent and one flat. Percent coupons apply first.
