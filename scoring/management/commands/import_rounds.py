import csv
import logging
from datetime import datetime

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from scoring.models import Course, Round, TeeSet


class Command(BaseCommand):
    help = "Imports golf rounds from a CSV file"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str)
        parser.add_argument(
            "--user",
            type=str,
            required=True,
            help="Username to associate with imported rounds",
        )
        parser.add_argument(
            "--location",
            type=str,
            default="Marion, MA",
            help="Default location for new courses",
        )

    def handle(self, *args, **options):
        try:
            user = User.objects.get(username=options["user"])
        except User.DoesNotExist as e:
            raise CommandError(f"User '{options['user']}' not found") from e

        required_fields = {"course name", "date", "gross score"}
        imported_count = 0
        skipped_count = 0

        try:
            with open(options["csv_file"], newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)

                # Validate CSV structure
                if not reader.fieldnames:
                    raise CommandError("CSV file is empty")

                if missing_fields := required_fields - set(reader.fieldnames or []):
                    raise CommandError(
                        f"CSV missing required fields: {', '.join(missing_fields)}"
                    )

                for row_num, row in enumerate(reader, start=2):
                    try:
                        # Validate and parse data
                        if not row["course name"]:
                            self.stdout.write(
                                f"Row {row_num}: Skipped (missing course name)"
                            )
                            skipped_count += 1
                            continue

                        course, _ = Course.objects.get_or_create(
                            name=row["course name"],
                            defaults={"location": options["location"]},
                        )

                        tee_name = row.get("tee name", "White").strip() or "White"
                        tee_set, _ = TeeSet.objects.get_or_create(
                            course=course,
                            color=tee_name,
                            defaults={"rating": 71.2, "slope": 113},
                        )

                        # Parse and validate score
                        try:
                            gross_score = int(row["gross score"])
                        except (ValueError, TypeError):
                            self.stdout.write(
                                f"Row {row_num}: Skipped (invalid score: {row['gross score']})"
                            )
                            skipped_count += 1
                            continue

                        # Parse date
                        try:
                            round_date = datetime.strptime(
                                row["date"], "%Y-%m-%d"
                            ).date()
                        except (ValueError, TypeError):
                            self.stdout.write(
                                f"Row {row_num}: Skipped (invalid date: {row['date']})"
                            )
                            skipped_count += 1
                            continue

                        # Create Round
                        round_obj = Round.objects.create(
                            user=user,
                            course=course,
                            tee_set=tee_set,
                            date=round_date,
                            gross_score=gross_score,
                        )
                        logging.info(f"Created round: {round_obj}")
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Imported round for {user.username} at {course.name} on {round_date} with score {gross_score}"
                            )
                        )

                        imported_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Row {row_num}: Imported {round_date} - "
                                f"{gross_score} at {course.name}"
                            )
                        )

                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f"Row {row_num}: Error - {str(e)}")
                        )
                        skipped_count += 1
                        continue

        except FileNotFoundError as exc:
            raise CommandError(f"CSV file not found: {options['csv_file']}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"\nImport complete: {imported_count} imported, {skipped_count} skipped"
            )
        )
