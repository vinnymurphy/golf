import csv
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from scoring.models import Course, Round, TeeSet


class Command(BaseCommand):
    help = "Imports golf rounds from a CSV file"

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str)

    def handle(self, *args, **options):
        # We'll assume 'vmurphy' is your user based on your system logs
        user = User.objects.get(username="vmurphy")

        with open(options["csv_file"], newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 1. Get or Create Course
                course, _ = Course.objects.get_or_create(
                    name=row["course name"], defaults={"location": "Marion, MA"}
                )

                # 2. Handle missing TeeSet info from CSV
                # For now, we'll default to 'White' if not specified
                tee_name = row["tee name"] if row["tee name"] else "White"
                tee_set, _ = TeeSet.objects.get_or_create(
                    course=course,
                    color=tee_name,
                    defaults={"rating": 71.2, "slope": 113},  # Placeholders
                )

                # 3. Create the Round
                new_round = Round.objects.create(
                    user=user,
                    course=course,
                    # You might need to add a date field to your Round model if you haven't!
                    # date=row["date"]
                )

                # 4. Log the Gross Score
                # Since the CSV doesn't have hole-by-hole, we might want to
                # store the 'gross score' in a summary field on the Round model
                # or create a dummy HoleScore for now.
                print(
                    f"Imported: {row['date']} - {row['gross score']} at {row['course name']}"
                )
