from .models import Round


def calculate_handicap(player_user):

    # 1. Get the 20 most recent rounds
    rounds = Round.objects.filter(user=player_user).order_by("-date_played")[:20]
    count = rounds.count()

    if count < 3:
        return None  # WHS usually requires at least 3 rounds to start

    # 2. Get the differentials and sort them (lowest is best)
    diffs = sorted([float(r.differential) for r in rounds])

    # 3. Determine how many differentials to use
    # (Standard WHS: 20 rounds = 8 diffs; 15-19 = 6; 12-14 = 4; etc.)
    if count >= 20:
        num_to_use = 8
    elif count >= 15:
        num_to_use = 6
    elif count >= 10:
        num_to_use = 3
    else:
        num_to_use = 1  # Minimum requirement

    best_diffs = diffs[:num_to_use]
    index = sum(best_diffs) / len(best_diffs)

    return round(index, 1)
