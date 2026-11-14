# feat(shipping): calculate shipping rates by zone based on pincode

Implement region-based shipping zones using Indian PIN code prefixes, charging different rates for south, north, west, east, northeast, and army postal regions while keeping free shipping for orders of ₹999 or more and quoting a standard ₹49 flat rate before a pincode is provided.

## Changes
- Added zone-based shipping rate calculation depending on the PIN code's first digit or northeast prefixes.
- Updated shipping_rate_for to accept an optional pincode, returning the standard flat rate when pincode is None or free shipping when the order amount meets or exceeds ₹999.
- Added new unit tests covering zone-based rates, free shipping across zones, and pre-pincode cart rate quotes.

## Functions
- `shoplite/services/shipping.py::zone_for_pincode` (implemented): Determines and returns the shipping zone string for a given PIN code by checking northeast prefixes first and then mapping the first digit.
- `shoplite/services/shipping.py::shipping_rate_for` (implemented): Calculates the shipping charge based on order amount and an optional PIN code, returning zero for free shipping thresholds, the flat rate if no pincode is provided, or the specific zone rate otherwise.

## Could not determine
- Nothing.

## Release note
Shipping is now priced by zone based on the PIN code's first digit (south ₹39, north/west ₹59, east ₹69, northeast/APS ₹99), with free shipping on orders of ₹999 or more and a standard ₹49 quote before checkout.
