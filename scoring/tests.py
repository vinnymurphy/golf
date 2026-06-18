import json
from datetime import date, timedelta

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


class PlayerProfileViewTests(TestCase):
    def test_profile_chart_shows_historical_handicaps(self):
        user = User.objects.create_user(
            username="vmurphy",
            first_name="Vincent",
            password="unused",
        )
        course = Course.objects.create(name="Pine Valley")
        start_date = date(2026, 5, 1)

        for offset, differential in enumerate(("20.00", "22.00", "24.00", "10.00")):
            Round.objects.create(
                user=user,
                course=course,
                date=start_date + timedelta(days=offset),
                total_gross_score=82 + offset,
                differential=differential,
            )

        response = self.client.get(
            reverse("scoring:player_profile", kwargs={"username": user.username})
        )

        self.assertEqual(response.status_code, 200)
        handicaps = json.loads(response.context["chart_handicaps_json"])

        self.assertEqual(handicaps, [None, None, 18.0, 9.0])
