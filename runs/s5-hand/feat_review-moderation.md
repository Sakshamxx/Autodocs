# feat(reviews): add customer flag moderation and admin hidden review list

Adds review moderation capabilities allowing customers to flag reviews with specific reasons. When a review receives three flags, its status is automatically changed to hidden. Admins can view a paginated list of hidden reviews.

## Changes
- Added a review_flags table and a status field to reviews via migration 0004.
- Added POST /reviews/<id>/flag endpoint for customers to report reviews.
- Added GET /reviews/hidden endpoint for administrators to list reviews hidden by flags.
- Updated public review listings and rating summaries to exclude hidden reviews.

## Functions
- `shoplite/api/reviews.py::flag_review` (implemented): Flags a review by ID with a given reason and returns its updated status and flag count.
- `shoplite/api/reviews.py::list_hidden_reviews` (implemented): Lists paginated reviews hidden by flags for authenticated administrators.
- `shoplite/services/reviews.py::review_query` (implemented): Returns a select query for published reviews of a product ordered newest first.
- `shoplite/services/reviews.py::rating_summary` (implemented): Calculates the average rating and review count for published reviews of a product.
- `shoplite/services/reviews.py::flag_review` (implemented): Records a review flag from a user, hiding the review if the flag count reaches the threshold.
- `shoplite/services/reviews.py::hidden_review_query` (implemented): Returns a select query for hidden reviews ordered by ID.
- `shoplite/services/reviews.py::score_review_text` (empty): Placeholder function for review text moderation scoring.

## Could not determine
- Nothing.

## Release note
Customers can flag reviews (POST /reviews/<id>/flag). Three flags hide a review; admins list hidden reviews at GET /reviews/hidden.
