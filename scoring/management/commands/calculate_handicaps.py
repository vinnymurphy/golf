from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from scoring.utils import calculate_handicap

class Command(BaseCommand):
    help = "Calculates and displays the current handicap for users"

    def add_arguments(self, parser):
        # Optional argument to calculate handicap for a specific user
        parser.add_argument(
            "--username", 
            type=str, 
            help="The username of a specific player"
        )

    def handle(self, *args, **options):
        username = options.get("username")

        if username:
            users = User.objects.filter(username=username)
        else:
            users = User.objects.all()

        for user in users:
            handicap = calculate_handicap(user)
            display_val = handicap if handicap is not None else "N/A (Not enough rounds)"
            
            self.stdout.write(
                self.style.SUCCESS(f"Handicap for {user.username}: {display_val}")
            )