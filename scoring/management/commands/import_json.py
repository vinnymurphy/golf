import json
import logging
import os

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
        """Validate that entry contains all required fields and valid data types."""
        required_fields = [
            "username",
            "course",
            "date",
            "total_gross_score",
            "completed_holes",
        ]
        if missing := [f for f in required_fields if f not in entry]:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

        # Validate numeric fields
        try:
            total_gross_score = int(entry["total_gross_score"])
            completed_holes = int(entry["completed_holes"])

            if total_gross_score <= 0:
                raise ValueError("total_gross_score must be a positive integer")
            if completed_holes < 1 or completed_holes > 18:
                raise ValueError("completed_holes must be between 1 and 18")
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid numeric field: {e}") from e

        # Validate username is a string
        if not isinstance(entry.get("username"), str) or not entry["username"].strip():
            raise ValueError("username must be a non-empty string")

        # Validate hole_scores if provided
        if entry.get("hole_scores"):
            if "tee_set_name" not in entry:
                raise ValueError(
                    "tee_set_name is required when hole_scores are provided"
                )
            if not isinstance(entry["hole_scores"], list):
                raise ValueError("hole_scores must be a list")

            # Validate each hole score is a positive integer
            if not entry["hole_scores"]:
                raise ValueError("hole_scores list cannot be empty")

            try:
                hole_scores = [int(s) for s in entry["hole_scores"]]
                if any(s <= 0 for s in hole_scores):
                    raise ValueError("All hole scores must be positive integers")
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    "All hole scores must be valid positive integers"
                ) from exc

    @transaction.atomic
    def _import_round(self, entry, verbose=False):
        """Import a single round with all associated data."""
        username = entry["username"].lower().strip()

        # Get or create user with validation
        try:
            user, created = User.objects.get_or_create(
                username=username, defaults={"is_active": True}
            )
            if created and verbose:
                logger.info(f"Created new user: {username}")
        except Exception as e:
            raise ValueError(f"Failed to create/retrieve user '{username}': {e}") from e

        # Get course
        try:
            course = Course.objects.get(name=entry["course"])
        except Course.DoesNotExist as exc:
            raise ValueError(
                f"Course '{entry['course']}' not found in database"
            ) from exc

        # Create the Round
        try:
            new_round = Round.objects.create(
                user=user,
                course=course,
                date=entry["date"],
                total_gross_score=entry["total_gross_score"],
                completed_holes=entry["completed_holes"],
            )
            if verbose:
                logger.info(f"Created round {new_round.id} for {username}")
        except Exception as e:
            raise ValueError(f"Failed to create round for {username}: {e}") from e

        # Add Hole Scores if they exist, then recalculate differential
        if entry.get("hole_scores"):
            self._import_hole_scores(new_round, entry, verbose)
            new_round.update_differential()
            new_round.save()

    def _import_hole_scores(self, round_obj, entry, verbose=False):
        """Import hole scores for a round."""
        hole_scores = entry["hole_scores"]

        # Try to get TeeSet by name first, then by color as fallback
        tee_set = None
        try:
            tee_set = TeeSet.objects.get(
                course=round_obj.course, name=entry["tee_set_name"]
            )
        except TeeSet.DoesNotExist:
            # Fallback: try to match by color
            try:
                tee_set = TeeSet.objects.get(
                    course=round_obj.course, color=entry["tee_set_name"]
                )
                if verbose:
                    logger.info(
                        f"Matched tee_set_name '{entry['tee_set_name']}' by color"
                    )
            except TeeSet.DoesNotExist as e:
                raise ValueError(
                    f"Tee set '{entry['tee_set_name']}' not found for course '{round_obj.course.name}' "
                    f"(checked both 'name' and 'color' fields)"
                ) from e

        # Fetch holes in order
        holes = list(
            Hole.objects.filter(tee_set=tee_set).order_by("hole_number")[
                : len(hole_scores)
            ]
        )

        if len(holes) != len(hole_scores):
            raise ValueError(
                f"Expected {len(hole_scores)} holes but only found {len(holes)} "
                f"in tee set '{entry['tee_set_name']}'"
            )

        # Validate total matches expected gross score
        total_hole_score = sum(hole_scores)
        if total_hole_score != entry["total_gross_score"]:
            raise ValueError(
                f"Total gross score {entry['total_gross_score']} does not match "
                f"sum of hole scores {total_hole_score}"
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
