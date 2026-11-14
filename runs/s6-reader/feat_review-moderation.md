# feat(reviews): add review moderation and flagging system

Adds customer review flagging and admin moderation capabilities. Reviews automatically become hidden after receiving three flags, and are excluded from public product ratings while hidden. Includes a new migration and API endpoints for flagging reviews and listing hidden ones.

## Changes
- Added status field to reviews and created review_flags table via migration 0004.
- Added POST /reviews/<id>/flag endpoint allowing customers to flag reviews with a valid reason.
- Added GET /reviews/hidden endpoint for administrators to view hidden reviews.
- Updated public product reviews and rating summaries to exclude hidden reviews.
- Added unit tests covering the flagging rules, auto-hiding behavior, and admin-only access.

## Functions
- `shoplite/api/reviews.py::flag_review` (implemented): Flags a review by ID with a given reason on behalf of the current user and returns its updated status and flag count.
- `shoplite/api/reviews.py::list_hidden_reviews` (implemented): Lists paginated reviews hidden by flags for administrators only.
- `shoplite/services/reviews.py::review_query` (implemented): Returns a query for published reviews for a product, ordered by creation date newest first.
- `shoplite/services/reviews.py::rating_summary` (implemented): Calculates the average rating and count of published reviews for a given product.
- `shoplite/services/reviews.py::flag_review` (implemented): Records a review flag from a user after validating reasons, ensuring users cannot flag their own or duplicate flags, and hides the review if the flag threshold is reached.
- `shoplite/services/reviews.py::hidden_review_query` (implemented): Returns a query for hidden reviews, ordered by ID oldest first.
- `shoplite/services/reviews.py::score_review_text` (empty): Placeholder function for scoring review text with a moderation model.

## Could not determine
- Nothing.

## Release note
Customers can flag reviews (POST /reviews/<id>/flag). Three flags hide a review; admins list hidden reviews at GET /reviews/hidden.
