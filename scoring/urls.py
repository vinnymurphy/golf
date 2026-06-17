from django.urls import path, register_converter

from . import views


# Custom URL converters for better type safety
class UsernameConverter:
    """Matches alphanumeric characters, hyphens, and underscores for
    usernames.
    """

    regex = r"[a-zA-Z0-9_-]+"

    @staticmethod
    def to_python(value):
        return str(value)

    @staticmethod
    def to_url(value):
        return str(value)


register_converter(UsernameConverter, "username")

# We use app_name for namespacing (e.g., 'scoring:leaderboard')
app_name = "scoring"

urlpatterns = [
    # Default: Global leaderboard
    path("", views.global_leaderboard, name="global_leaderboard"),
    # Rounds - GET: List all rounds | POST: Create new round
    path("rounds/", views.RoundListView.as_view(), name="round_list"),
    path("add/", views.add_round, name="add_round"),
    path("round/<int:round_id>/", views.round_detail, name="round_detail"),
    path("start-round/", views.start_round, name="start_round"),
    path(
        "enter-scorecard/<int:course_id>/",
        views.enter_scorecard,
        name="enter_scorecard",
    ),
    path(
        "enter-scores/<int:round_id>/",
        views.enter_scores,
        name="enter_scores",
    ),
    path(
        "setup-holes/<int:course_id>/",
        views.setup_course_holes,
        name="setup_holes",
    ),
    path(
        "leaderboard/<slug:slug>/",
        views.leaderboard_view,
        name="leaderboard_detail",
    ),
    path(
        "profile/<username:username>/",
        views.player_profile,
        name="player_profile",
    ),
    # AJAX endpoints - Asynchronous data loading
    path("ajax/load-tees/", views.load_tees, name="ajax_load_tees"),
]
