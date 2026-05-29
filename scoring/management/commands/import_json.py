import json
import logging
import os
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from scoring.models import Course, Hole, HoleScore, Round, TeeSet

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Imports golf rounds from a JSON file"

    def add_arguments(self, parser):
        parser.add_argument("json_file", type=str, help="Path to the JSON file")
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Enable verbose output for debugging",
        )

    def handle(self, *args, **options):
        file_path = options["json_file"]
        verbose = options.get("verbose", False)

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"File {file_path} not found"))
            return

        try:
            with open(file_path, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            self.stdout.write(self.style.ERROR(f"Invalid JSON file: {e}"))
            return

        if not isinstance(data, list):
            self.stdout.write(
                self.style.ERROR("JSON must contain a list of round entries")
            )
            return

        imported_count = 0
        failed_count = 0

        for idx, entry in enumerate(data, start=1):
            try:
                self._validate_entry(entry)
                self._import_round(entry, verbose)
                imported_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Imported round for {entry['username']}")
                )
            except ValueError as e:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"✗ Row {idx}: {entry.get('username', 'unknown')} - {e}"
                    )
                )
                if verbose:
                    logger.exception(f"Detailed error for row {idx}")
            except Exception as e:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"✗ Row {idx}: {entry.get('username', 'unknown')} - Unexpected error: {e}"
                    )
                )
                if verbose:
                    logger.exception(f"Detailed error for row {idx}")

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(
            self.style.SUCCESS(f"Successfully imported: {imported_count}")
        )
        if failed_count > 0:
            self.stdout.write(self.style.WARNING(f"Failed: {failed_count}"))

    def _validate_entry(self, entry):
        """Validate that entry contains all required fields."""
        required_fields = [
            "username",
            "course",
            "date",
            "total_gross_score",
            "completed_holes",
        ]
        if missing := [f for f in required_fields if f not in entry]:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

        # Validate hole_scores if provided
        if entry.get("hole_scores"):
            if "tee_set_name" not in entry:
                raise ValueError(
                    "tee_set_name is required when hole_scores are provided"
                )
            if not isinstance(entry["hole_scores"], list):
                raise ValueError("hole_scores must be a list")

    @transaction.atomic
    def _import_round(self, entry, verbose=False):
        """Import a single round with all associated data."""
        username = entry["username"].lower()

        # Get or validate user
        user, created = User.objects.get_or_create(
            username=username, defaults={"is_active": True}
        )
        if created:
            if verbose:
                print(f"Created new user: {username}")
        try:
            course = Course.objects.get(name=entry["course"])
        except Course.DoesNotExist as exc:
            raise ValueError(
                f"Course '{entry['course']}' not found in database"
            ) from exc

        # Create the Round
        new_round = Round.objects.create(
            user=user,
            course=course,
            date=entry["date"],
            total_gross_score=entry["total_gross_score"],
            completed_holes=entry["completed_holes"],
        )

        if verbose:
            logger.info(f"Created round {new_round.id} for {username}")

        # Add Hole Scores if they exist
        if entry.get("hole_scores"):
            self._import_hole_scores(new_round, entry, verbose)

        if new_round.differential is None or new_round.differential == Decimal("0.00"):
            new_round.update_differential()

    def _import_hole_scores(self, round_obj, entry, verbose=False):
        """Import hole scores for a round."""
        hole_scores = entry["hole_scores"]

        try:
            tee_set = TeeSet.objects.get(
                course=round_obj.course, name=entry["tee_set_name"]
            )
        except TeeSet.DoesNotExist as e:
            raise ValueError(
                f"Tee set '{entry['tee_set_name']}' not found for course '{round_obj.course.name}'"
            ) from e

        # Fetch holes in order
        holes = list(
            Hole.objects.filter(tee_set=tee_set).order_by("hole_number")[
                : len(hole_scores)
            ]
        )

        if len(holes) != len(hole_scores):
            raise ValueError(
                f"Expected {len(hole_scores)} holes but only found {len(holes)} in tee set '{entry['tee_set_name']}'"
            )

        # Validate total
        total_hole_score = sum(hole_scores)
        if total_hole_score != entry["total_gross_score"]:
            raise ValueError(
                f"Total gross score {entry['total_gross_score']} does not match sum of hole scores {total_hole_score}"
            )

        # Bulk create hole scores for performance
        hole_score_objects = [
            HoleScore(round=round_obj, hole=hole, strokes=score_val)
            for hole, score_val in zip(holes, hole_scores)
        ]
        HoleScore.objects.bulk_create(hole_score_objects)

        if verbose:
            logger.info(
                f"Created {len(hole_score_objects)} hole scores for round {round_obj.id}"
            )
