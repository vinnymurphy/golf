from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from scoring.models import Round
from scoring.utils import calculate_handicap


class Command(BaseCommand):
    help = "Calculates and displays the current handicap for users"

    def add_arguments(self, parser):
        # Optional argument to calculate handicap for a specific user
        parser.add_argument(
            "--username", type=str, help="The username of a specific player"
        )

    def handle(self, *args, **options):
        username = options.get("username")
        all_users = options.get("all_users")

        if username:
            users = User.objects.filter(username=username)
        else:
            users = User.objects.all()
        total_recalculated = 0

        for user in users:
            if all_users or not username:
                rounds_to_fix = Round.objects.filter(
                    user=user, differential__in=[None, Decimal("0.0")]
                )
            else:
                rounds_to_fix = Round.objects.filter(player=user)

            for round_obj in rounds_to_fix:
                result = round_obj.update_differential()
                if result is not None:
                    round_obj.save()
                    total_recalculated += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ {user.username} - {round_obj.date}: {result}"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"⚠ {user.username} - {round_obj.date}: Could not calculate"
                        )
                    )
            handicap = calculate_handicap(user)
            display_val = (
                handicap if handicap is not None else "N/A (Not enough rounds)"
            )

            self.stdout.write(
                self.style.SUCCESS(f"Handicap for {user.username}: {display_val}")
            )

        self.stdout.write(
            self.style.SUCCESS(f"\nRecalculated {total_recalculated} differentials")
        )
