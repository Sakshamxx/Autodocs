# feat(reviews): add review flagging and admin moderation

Introduces review moderation, allowing authenticated customers to flag reviews with predefined reasons. Accumulating three flags automatically hides a review from product listings and calculations, and administrators can review hidden reports at a new endpoint.

## Changes
- Added a review_flags table and status column on reviews via database migration 0004.
- Added POST /reviews/<id>/flag endpoint allowing users to flag reviews subject to validation rules.
- Added GET /reviews/hidden endpoint for administrators to list and inspect hidden reviews.
- Filtered out hidden reviews from product review lists and rating summaries.
- Added validation rules ensuring authors cannot flag their own reviews and users cannot flag the same review twice.

## Functions
- `shoplite/api/reviews.py::flag_review` (implemented): Flags a review by ID for the current authenticated user with a given reason.
- `shoplite/api/reviews.py::list_hidden_reviews` (implemented): Lists hidden reviews for administrators with pagination and flag counts.
- `shoplite/services/reviews.py::review_query` (implemented): Returns a query for published reviews for a product, ordered newest first.
- `shoplite/services/reviews.py::rating_summary` (implemented): Computes rating count and average rating for published reviews of a product.
- `shoplite/services/reviews.py::flag_review` (implemented): Records a user flag on a review and hides the review if the flag count reaches the threshold.
- `shoplite/services/reviews.py::hidden_review_query` (implemented): Returns a query selecting hidden reviews ordered by ID.
- `shoplite/services/reviews.py::score_review_text` (empty): Placeholder function for review moderation scoring that is not yet implemented.

## Could not determine
- Nothing.

## Release note
Customers can flag reviews (POST /reviews/<id>/flag). Three flags hide a review; admins list hidden reviews at GET /reviews/hidden.
