from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Course, Round, TeeSet


class LeaderboardViewTests(TestCase):
    def test_global_leaderboard_renders_players(self):
        user = User.objects.create_user(
            username="vmurphy",
            first_name="Vincent",
            password="unused",
        )
        course = Course.objects.create(name="Pine Valley")
        TeeSet.objects.create(
            course=course,
            name="White",
            color="White",
            rating="72.0",
            slope=113,
        )
        Round.objects.create(
            user=user,
            course=course,
            total_gross_score=82,
        )

        response = self.client.get(reverse("scoring:global_leaderboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vincent")
        self.assertContains(response, "82")
