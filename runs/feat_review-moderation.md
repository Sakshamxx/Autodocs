# feat(reviews): add review moderation and flagging system

This branch introduces a moderation system for customer reviews, allowing users to flag reviews with valid reasons. When a review receives three flags, its status updates to hidden, removing it from public product pages and ratings while allowing administrators to review hidden entries via a dedicated endpoint.

## Changes
- Added a review_flags table and a review status column via database migration 0004.
- Added POST /reviews/<id>/flag endpoint allowing authenticated customers to flag reviews with specific reasons.
- Added GET /reviews/hidden endpoint for administrators to list reviews hidden by flags.
- Updated review queries and rating summary computations to exclude hidden reviews.
- Added comprehensive unit tests covering flagging rules, hidden review limits, and role access.

## Functions
- `shoplite/api/reviews.py::flag_review` (implemented): Flags a specific review with a provided reason after validating its existence.
- `shoplite/api/reviews.py::list_hidden_reviews` (implemented): Returns a paginated list of hidden reviews for authenticated administrators.
- `shoplite/services/reviews.py::review_query` (implemented): Returns a query for published reviews of a product ordered by newest first.
- `shoplite/services/reviews.py::rating_summary` (implemented): Calculates the total count and rounded average rating for published reviews of a product.
- `shoplite/services/reviews.py::flag_review` (implemented): Records a user flag on a review and hides the review if the flag threshold is reached.
- `shoplite/services/reviews.py::hidden_review_query` (implemented): Returns a query for hidden reviews ordered by ID in ascending order.
- `shoplite/services/reviews.py::score_review_text` (empty): Placeholder function for scoring review text that is not yet implemented.

## Could not determine
- Nothing.

## Release note
Customers can flag reviews (POST /reviews/<id>/flag). Three flags hide a review; admins list hidden reviews at GET /reviews/hidden.
