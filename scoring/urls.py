from django.urls import path

from . import views

# We use app_name for namespacing (e.g., 'scoring:leaderboard')
app_name = "scoring"

# scoring/urls.py

urlpatterns = [
    path("add/", views.add_round, name="add_round"),
    path("round/<int:round_id>/", views.round_detail, name="round_detail"),
    path("leaderboard/", views.leaderboard_view, name="leaderboard"),
    path("ajax/load-tees/", views.load_tees, name="ajax_load_tees"),
    path("start-round/", views.start_round, name="start_round"),
    path("profile/<str:username>/", views.player_profile, name="player_profile"),
]
