from django.urls import path
from . import views

# We use app_name for namespacing (e.g., 'scoring:leaderboard')
app_name = "scoring"

urlpatterns = [
    # Placeholder for the main scoring dashboard
    path("", views.index, name="index"),
    # Example: /scoring/round/5/
    path("round/<int:round_id>/", views.round_detail, name="round_detail"),
    # Example: /scoring/leaderboard/
    path("leaderboard/", views.leaderboard, name="leaderboard"),
]
