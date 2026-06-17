"""
Scoring app URL configuration.

Routes are organized into logical groups:
- Leaderboards: Global and player-specific rankings
- Rounds: CRUD operations for golf rounds
- Scoring: Data entry and scorecard management
- Courses: Course configuration (holes, tees)
- Players: Player profiles and statistics
- AJAX: Asynchronous data loading for frontend interactions
"""

from django.urls import path, register_converter

from . import views


# Custom URL converters for better type safety
class UsernameConverter:
    """Matches alphanumeric characters, hyphens, and underscores for usernames.

    Pattern constraints:
    - Length: 1-150 characters (matches Django User model)
    - Characters: alphanumeric, hyphens, and underscores
    """

    regex = r"[a-zA-Z0-9_-]{1,150}"

    @staticmethod
    def to_python(value):
        return str(value)

    @staticmethod
    def to_url(value):
        return str(value)


register_converter(UsernameConverter, "username")

# App namespacing for URL reversing (e.g., 'scoring:round_list')
app_name = "scoring"

urlpatterns = [
    # ========== LEADERBOARDS ==========
    path("", views.global_leaderboard, name="global_leaderboard"),
    path("leaderboard/<slug:slug>/", views.leaderboard_view, name="leaderboard_detail"),
    # ========== ROUNDS ==========
    path("rounds/", views.RoundListView.as_view(), name="round_list"),
    path("rounds/add/", views.add_round, name="add_round"),
    path("rounds/<int:round_id>/", views.round_detail, name="round_detail"),
    path("rounds/<int:round_id>/start/", views.start_round, name="start_round"),
    path("rounds/<int:round_id>/scores/", views.enter_scores, name="enter_scores"),
    # ========== COURSES & SETUP ==========
    path(
        "courses/<int:course_id>/scorecard/",
        views.enter_scorecard,
        name="enter_scorecard",
    ),
    path(
        "courses/<int:course_id>/setup-holes/",
        views.setup_course_holes,
        name="setup_holes",
    ),
    # ========== PLAYERS ==========
    path("profile/<username:username>/", views.player_profile, name="player_profile"),
    # ========== AJAX ENDPOINTS ==========
    # Asynchronous data loading for frontend interactions
    path("ajax/load-tees/", views.load_tees, name="ajax_load_tees"),
]
