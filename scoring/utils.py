from decimal import Decimal

from .models import Round


def _num_differentials_to_use(count: int) -> int | None:
    """Return number of differentials to use per WHS rules for a given round count."""
    if count < 3:
        return None

    # Mapping from number of rounds to number of differentials to use
    mapping = {
        3: 1,
        4: 1,
        5: 1,
        6: 2,
        7: 2,
        8: 3,
        9: 3,
        10: 3,
        11: 4,
        12: 4,
        13: 5,
        14: 5,
        15: 6,
        16: 6,
        17: 7,
        18: 7,
    }

    if count in mapping:
        return mapping[count]

    # 19 and 20+ use 8 differentials
    return 8 if count >= 19 else None


def calculate_handicap(player_user):
    """Calculate a player's WHS-style handicap index from their recent rounds."""

    # 1. Get the 20 most recent rounds
    all_rounds = Round.objects.filter(user=player_user).order_by("-date")[:20]

    # 2. Filter out rounds where differential is None or 0.00
    valid_rounds = [
        r
        for r in all_rounds
        if r.differential is not None and r.differential != Decimal("0.00")
    ]

    count = len(valid_rounds)
    num_to_use = _num_differentials_to_use(count)

    if num_to_use is None:
        return None

    # 3. Get the differentials and sort them (lowest is best)
    diffs = sorted(float(r.differential) for r in valid_rounds)

    # Ensure num_to_use doesn't exceed the number of available differentials
    num_to_use = min(num_to_use, len(diffs))
    if num_to_use == 0:
        return None

    best_diffs = diffs[:num_to_use]
    index = sum(best_diffs) / num_to_use

    return round(index, 1)
