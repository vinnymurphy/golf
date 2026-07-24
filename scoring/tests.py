import json
import tempfile
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Course, Hole, HoleScore, Round, TeeSet


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


class BulkRoundEntryTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin", password="pw")
        self.player_one = User.objects.create_user(
            username="alice", first_name="Alice", password="pw"
        )
        self.player_two = User.objects.create_user(
            username="bob", first_name="Bob", password="pw"
        )
        self.course = Course.objects.create(name="Pine Valley")
        self.tee_set = TeeSet.objects.create(
            course=self.course,
            name="White",
            color="White",
            rating="72.0",
            slope=113,
        )
        for hole_number in range(1, 19):
            Hole.objects.create(
                tee_set=self.tee_set,
                hole_number=hole_number,
                par=4,
                yardage=350,
            )
        self.client.force_login(self.admin)

    def test_bulk_total_scores_create_rounds_for_selected_players(self):
        response = self.client.post(
            reverse("scoring:bulk_add_rounds"),
            {
                "course": self.course.id,
                "tee_set": self.tee_set.id,
                "date": "2026-07-01",
                "entry_mode": "total",
                "players": [self.player_one.id, self.player_two.id],
                f"total_score_{self.player_one.id}": "82",
                f"holes_played_{self.player_one.id}": "18",
                f"total_score_{self.player_two.id}": "41",
                f"holes_played_{self.player_two.id}": "9",
            },
        )

        self.assertRedirects(response, reverse("scoring:round_list"))
        self.assertEqual(Round.objects.filter(course=self.course).count(), 2)
        alice_round = Round.objects.get(user=self.player_one)
        bob_round = Round.objects.get(user=self.player_two)
        self.assertEqual(alice_round.tee_set, self.tee_set)
        self.assertEqual(alice_round.total_gross_score, 82)
        self.assertEqual(alice_round.completed_holes, 18)
        self.assertEqual(bob_round.total_gross_score, 41)
        self.assertEqual(bob_round.completed_holes, 9)

    def test_bulk_hole_scores_create_round_and_hole_scores(self):
        post_data = {
            "course": self.course.id,
            "tee_set": self.tee_set.id,
            "date": "2026-07-01",
            "entry_mode": "holes",
            "players": [self.player_one.id],
        }
        for hole_number in range(1, 10):
            post_data[f"hole_{self.player_one.id}_{hole_number}"] = "4"

        response = self.client.post(reverse("scoring:bulk_add_rounds"), post_data)

        self.assertRedirects(response, reverse("scoring:round_list"))
        round_obj = Round.objects.get(user=self.player_one)
        self.assertEqual(round_obj.total_gross_score, 36)
        self.assertEqual(round_obj.completed_holes, 9)
        self.assertEqual(HoleScore.objects.filter(round=round_obj).count(), 9)


class ImportJsonTests(TestCase):
    def test_total_score_only_nine_hole_round_uses_named_tee_for_differential(self):
        course = Course.objects.create(name="Rochester Golf Club")
        tee_set = TeeSet.objects.create(
            course=course,
            name="White",
            color="White",
            rating="72.0",
            slope=113,
        )
        data = [
            {
                "username": "john",
                "course": course.name,
                "date": "2026-07-24",
                "total_gross_score": 37,
                "completed_holes": 9,
                "hole_scores": [],
                "tee_set_name": tee_set.name,
            }
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as json_file:
            json.dump(data, json_file)
            json_file.flush()
            call_command("import_json", json_file.name)

        round_obj = Round.objects.get(user__username="john")
        self.assertEqual(round_obj.tee_set, tee_set)
        self.assertEqual(round_obj.differential, 1)
