from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from scoring.models import Round
from scoring.utils import calculate_handicap


class Command(BaseCommand):
    help = "Calculates handicaps and optionally recalculates differentials"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username", type=str, help="The username of a specific player"
        )
        parser.add_argument(
            "--recalc-differentials",
            action="store_true",
            help="Recalculate differentials for rounds with missing/zero values",
        )

    def handle(self, *args, **options):
        username = options.get("username")
        recalc = options.get("recalc_differentials", False)

        users = (
            User.objects.filter(username=username) if username else User.objects.all()
        )
        total_recalculated = 0

        for user in users:
            if recalc:
                rounds_to_fix = Round.objects.filter(
                    user=user, differential__in=[None, Decimal("0.0")]
                )
                rounds_to_save = []

                for round_obj in rounds_to_fix:
                    result = round_obj.update_differential()
                    if result is not None:
                        rounds_to_save.append(round_obj)
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

                if rounds_to_save:
                    Round.objects.bulk_update(rounds_to_save, ["differential"])

            result = calculate_handicap(user)
            handicap = result.index
            display_val = (
                handicap if handicap is not None else "N/A (Not enough rounds)"
            )

            self.stdout.write(
                self.style.SUCCESS(f"Handicap for {user.username}: {display_val}")
            )

        if recalc:
            self.stdout.write(
                self.style.SUCCESS(f"\nRecalculated {total_recalculated} differentials")
            )
