from django.contrib.auth.models import User

from .models import Round


def _num_differentials_to_use(count: int) -> tuple[int, float] | None:
    """
    Returns a tuple of (number_of_differentials_to_use, adjustment_modifier)
    per official WHS rules based on total valid rounds played.
    """
    # WHS Sliding Scale: Map total_rounds -> (num_to_use, adjustment)
    whs_table = {
        3: (1, -2.0),
        4: (1, -1.0),
        5: (1, 0.0),
        6: (2, -1.0),
        7: (2, 0.0),
        8: (2, 0.0),
        9: (3, 0.0),
        10: (3, 0.0),
        11: (3, 0.0),
        12: (4, 0.0),
        13: (4, 0.0),
        14: (4, 0.0),
        15: (5, 0.0),
        16: (5, 0.0),
        17: (6, 0.0),
        18: (7, 0.0),
        19: (7, 0.0),
        20: (8, 0.0),
    }
    return None if count < 3 else whs_table.get(count, (8, 0.0))


# scoring/utils.py


def calculate_handicap(player_input):
    if isinstance(player_input, User):
        all_rounds = Round.objects.filter(user=player_input).order_by("-date")
    else:
        all_rounds = player_input.order_by("-date")

    valid_rounds = [r for r in all_rounds if r.differential is not None]
    total_valid = len(valid_rounds)

    # 1. Fetch the rules config (could be a tuple or None)
    rules = _num_differentials_to_use(total_valid)

    # 💡 FIX: Check if rules is None BEFORE trying to unpack it!
    if rules is None:
        return "N/A", set()

    # 2. Safely unpack now that we know it's a valid tuple
    num_to_use, adjustment = rules

    # 3. Sort and slice actual objects to preserve database row IDs
    sorted_rounds = sorted(valid_rounds, key=lambda r: float(r.differential))
    counting_rounds = sorted_rounds[:num_to_use]
    counting_ids = {r.id for r in counting_rounds}

    # 4. Calculate average and apply the WHS adjustment modifier
    total_diff = sum(float(r.differential) for r in counting_rounds)
    average_diff = total_diff / num_to_use
    final_index = round(average_diff + adjustment, 1)

    return final_index, counting_ids
