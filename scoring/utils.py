from dataclasses import dataclass

from django.contrib.auth.models import User
from django.db.models.query import QuerySet

from .models import Round

# WHS Sliding Scale: Map total_rounds -> (num_to_use, adjustment_modifier)
WHS_SLIDING_SCALE = {
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

DEFAULT_NUM_ROUNDS = 8
DEFAULT_ADJUSTMENT = 0.0
MINIMUM_VALID_ROUNDS = 3


@dataclass
class HandicapResult:
    """Result of handicap calculation."""
    index: float | None
    counting_round_ids: set[int]

    def __str__(self) -> str:
        """Return formatted handicap index or 'N/A' if unavailable."""
        return "N/A" if self.index is None else str(self.index)


def _num_differentials_to_use(count: int) -> tuple[int, float] | None:
    """
    Returns a tuple of (number_of_differentials_to_use, adjustment_modifier)
    per official WHS rules based on total valid rounds played.

    Args:
        count: Total number of valid rounds played.

    Returns:
        A tuple of (num_rounds_to_use, adjustment) or None if fewer than 3 valid rounds.
    """
    if count < MINIMUM_VALID_ROUNDS:
        return None

    return WHS_SLIDING_SCALE.get(
        count,
        (DEFAULT_NUM_ROUNDS, DEFAULT_ADJUSTMENT),
    )


def _get_rounds_queryset(player_input: User | QuerySet) -> QuerySet:
    """
    Get rounds queryset, handling both User and QuerySet inputs.

    Args:
        player_input: Either a User instance or a QuerySet of Round objects.

    Returns:
        A QuerySet of rounds ordered by date (newest first).
    """
    if isinstance(player_input, User):
        return Round.objects.filter(user=player_input).order_by("-date")
    return player_input.order_by("-date")


def calculate_handicap(player_input: User | QuerySet) -> HandicapResult:
    """
    Calculate the WHS handicap index and identify the counting rounds.

    This function evaluates a player's scoring differentials and applies the
    WHS sliding scale to determine the handicap index and which rounds are used.

    Args:
        player_input: A User instance or QuerySet of Round objects.

    Returns:
        HandicapResult containing the handicap index and IDs of rounds used in the calculation.
        Returns HandicapResult(index=None, counting_round_ids=set()) if fewer than 3 valid rounds exist.

    Example:
        >>> result = calculate_handicap(user)
        >>> print(result.index)
        12.5
        >>> print(result.counting_round_ids)
        {1, 2, 3}
    """
    all_rounds = _get_rounds_queryset(player_input)
    valid_rounds = list(all_rounds.exclude(differential__isnull=True))
    total_valid = len(valid_rounds)

    # Fetch the rules config (could be a tuple or None)
    rules = _num_differentials_to_use(total_valid)

    if rules is None:
        return HandicapResult(index=None, counting_round_ids=set())

    num_to_use, adjustment = rules

    # Validate that num_to_use is positive to avoid division by zero
    if num_to_use <= 0:
        return HandicapResult(index=None, counting_round_ids=set())

    # Sort rounds by differential (lowest first) and select the best ones
    sorted_rounds = sorted(
        valid_rounds,
        key=lambda r: float(r.differential),
    )
    counting_rounds = sorted_rounds[:num_to_use]
    counting_ids = {r.id for r in counting_rounds}

    # Calculate average differential and apply WHS adjustment
    total_diff = sum(float(r.differential) for r in counting_rounds)
    average_diff = total_diff / num_to_use
    final_index = round(average_diff + adjustment, 1)

    return HandicapResult(index=final_index, counting_round_ids=counting_ids)
