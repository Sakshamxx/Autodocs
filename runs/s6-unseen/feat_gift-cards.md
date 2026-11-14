# feat(gift-cards): add gift card support for checkout and refunds

Adds a gift card system where admins can issue cards, customers can check balances, and checkout allows paying with an optional gift card alongside the main payment method. Any refunded order also returns the gift card portion back to the gift card balance.

## Changes
- Added GiftCard model and database migration 0004.
- Added POST /gift-cards for admins to issue gift cards and GET /gift-cards/<code> for balance checks.
- Updated checkout to accept an optional gift_card_code, apply the balance towards the order total, and handle full gift card coverage without gateway charges.
- Updated order refunds to restore spent gift card balances back to the respective gift cards.

## Functions
- `shoplite/api/gift_cards.py::issue` (implemented): Validates admin permissions and request parameters to issue a new gift card.
- `shoplite/api/gift_cards.py::balance` (implemented): Retrieves and returns the balance and details of a gift card by code.
- `shoplite/api/orders.py::place_order` (implemented): Places an order from the cart, now passing an optional gift card code to checkout.
- `shoplite/models/gift_card.py::GiftCard.to_dict` (implemented): Returns a dictionary serialization of the gift card.
- `shoplite/services/checkout.py::record_failed_payment` (implemented): Marks an order as failed and records the remaining payment amount after gift card coverage.
- `shoplite/services/checkout.py::checkout` (implemented): Executes the cart checkout process, applying gift card coverage and charging the remaining balance via payment gateway.
- `shoplite/services/gift_cards.py::issue_gift_card` (implemented): Creates and persists a new gift card with a unique code and specified amount.
- `shoplite/services/gift_cards.py::get_gift_card` (implemented): Finds and returns a gift card by its code or raises a NotFound error.
- `shoplite/services/gift_cards.py::usable_card` (implemented): Validates that a gift card exists, is active, has remaining balance, and has not expired.
- `shoplite/services/gift_cards.py::amount_covered` (implemented): Calculates how much of the order total can be paid by the gift card balance.
- `shoplite/services/refunds.py::refund_order` (implemented): Refunds a paid or shipped order by refunding the gateway payment and restoring the gift card balance.

## Could not determine
- Nothing.

## Release note
Add gift cards: admins can issue cards via POST /gift-cards, and checkout now accepts a gift_card_code to partially or fully cover order totals.
