import json
from functools import lru_cache

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Avg, Min, Prefetch
from django.forms import inlineformset_factory
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView

from .forms import HoleScoreFormSet, RoundForm
from .models import Course, Hole, HoleScore, Round, TeeSet
from .utils import calculate_handicap

# ============================================================================
# Constants
# ============================================================================
GOLF_HOLES = 18
RECENT_ROUNDS_DISPLAY = 20
RECENT_ROUNDS_TREND = 3
RECENT_GLOBAL_ROUNDS = 8
HANDICAP_DEFAULT_SORT_VALUE = 999.0
HANDICAP_DEFAULT_DISPLAY = "N/A"
PAGINATION_PAGE_SIZE = 20


# ============================================================================
# Helper Functions
# ============================================================================


def _get_numeric_handicap(handicap_value, default=None):
    """
    Convert handicap value to float, with fallback for "N/A".

    Args:
        handicap_value: The handicap index value
        default: Value to return if handicap is "N/A" or None

    Returns:
        float or the default value
    """
    if handicap_value == HANDICAP_DEFAULT_DISPLAY or handicap_value is None:
        return default if default is not None else HANDICAP_DEFAULT_SORT_VALUE
    return float(handicap_value)


def _build_player_chart_data(player, recent_rounds):
    """
    Build chart data for player profile (dates, scores, handicaps).

    Efficiently calculates handicaps for each round by computing them
    once for all historical data up to each date, avoiding N+1 queries.

    Args:
        player: User object
        recent_rounds: QuerySet of recent Round objects (ordered ascending by date)

    Returns:
        tuple: (chart_dates, chart_scores, chart_handicaps)
    """
    chart_dates = []
    chart_scores = []
    chart_handicaps = []

    # Get all rounds up to the last round in recent_rounds for efficiency
    if not recent_rounds.exists():
        return chart_dates, chart_scores, chart_handicaps

    last_date = recent_rounds.last().date
    all_history = Round.objects.filter(
        user=player, date__lte=last_date
    ).select_related("course").order_by("date")

    # Build a date -> handicap map by processing all history in order
    handicap_cache = {}
    for round_obj in all_history:
        # Calculate handicap for all rounds up to this date
        history_up_to = all_history.filter(date__lte=round_obj.date)
        h_result = calculate_handicap(history_up_to)
        handicap_cache[round_obj.date] = h_result.index

    # Now populate chart data from recent_rounds only
    for round_obj in recent_rounds:
        chart_dates.append(round_obj.date.strftime("%b %d, %Y"))

        # Add score if available
        if round_obj.total_gross_score is not None:
            chart_scores.append(round_obj.total_gross_score)
        else:
            chart_scores.append(None)

        # Use cached handicap
        h_index = handicap_cache.get(round_obj.date)
        if h_index is not None and h_index != HANDICAP_DEFAULT_DISPLAY:
            chart_handicaps.append(float(h_index))
        else:
            chart_handicaps.append(None)

    return chart_dates, chart_scores, chart_handicaps


def _calculate_form_trend(recent_rounds, handicap_index):
    """Calculate form trend (average of recent rounds vs overall
    handicap).

    Args:
        recent_rounds: QuerySet of recent Round objects
        handicap_index: Player's current handicap index (float or None)

    Returns:
        float or None: Trend metric or None if not enough rounds

    """
    if recent_rounds.count() < RECENT_ROUNDS_TREND:
        return None

    valid_differentials = [
        float(r.differential)
        for r in recent_rounds
        if r.differential is not None
    ]

    if not valid_differentials:
        return None

    recent_avg = sum(valid_differentials) / len(valid_differentials)

    # Guard against None handicap_index
    if handicap_index is not None and handicap_index != HANDICAP_DEFAULT_DISPLAY:
        return round(recent_avg - float(handicap_index), 1)

    return None


def _build_leaderboard_entry(buddy, handicap, recent_scores):
    """
    Build a single leaderboard entry.

    Args:
        buddy: User object
        handicap: Handicap index value (float or None)
        recent_scores: List of recent scores

    Returns:
        dict: Leaderboard entry
    """
    handicap_display = handicap if handicap is not None else HANDICAP_DEFAULT_DISPLAY

    return {
        "user": buddy,
        "handicap": handicap_display,
        "recent_scores": recent_scores,
        "sort_val": _get_numeric_handicap(handicap_display),
    }


def _build_course_leaderboard_data(course=None):
    """
    Build leaderboard data for a specific course or globally.

    Optimized with select_related() and prefetch_related() to minimize queries.

    Args:
        course: Course object or None for global leaderboard

    Returns:
        list: Sorted leaderboard data
    """
    if course:
        player_ids = (
            Round.objects.filter(course=course)
            .values_list("user_id", flat=True)
            .distinct()
        )
    else:
        player_ids = Round.objects.values_list("user", flat=True).distinct()

    # Optimize: use Prefetch with select_related to reduce queries
    round_queryset = Round.objects.select_related("course").order_by("-date")
    buddies = User.objects.filter(id__in=player_ids).prefetch_related(
        Prefetch("round_set", queryset=round_queryset)
    )

    leaderboard_data = []

    for buddy in buddies:
        handicap_result = calculate_handicap(buddy)
        handicap = handicap_result.index

        if course:
            recent_rounds = [
                r for r in buddy.round_set.all() if r.course_id == course.id
            ]
            recent_scores = [r.total_score for r in recent_rounds]
        else:
            recent_rounds = list(buddy.round_set.all())[:RECENT_GLOBAL_ROUNDS]
            recent_scores = [
                {"score": r.total_score, "course": r.course.name}
                for r in recent_rounds
            ]

        leaderboard_data.append(
            _build_leaderboard_entry(buddy, handicap, recent_scores)
        )

    # Sort by handicap (lowest to highest)
    leaderboard_data.sort(key=lambda x: _get_numeric_handicap(x["handicap"]))

    return leaderboard_data


# ============================================================================
# Views
# ============================================================================


def index(request):
    return HttpResponse("Welcome to the Golf Scoring Dashboard!")


def leaderboard(request):
    return HttpResponse("Global Golf Leaderboard")


class RoundListView(ListView):
    model = Round
    template_name = "scoring/round_list.html"
    context_object_name = "rounds"
    ordering = ["-date"]
    paginate_by = PAGINATION_PAGE_SIZE


def round_detail(request, round_id):
    """
    Display details for a specific round.
    """
    round_obj = get_object_or_404(Round, pk=round_id)
    hole_scores = (
        round_obj.scores.all().select_related("hole").order_by("hole__hole_number")
    )

    context = {
        "round": round_obj,
        "hole_scores": hole_scores,
        "total": round_obj.total_score,
        "relative_to_par": round_obj.total_score - round_obj.total_par,
    }

    return render(request, "scoring/round_detail.html", context)


def player_profile(request, username):
    """
    Display player profile with stats, recent rounds, and trend charts.

    Optimized with efficient queries and pagination for large datasets.
    """
    player = get_object_or_404(User, username=username)
    all_user_rounds = Round.objects.filter(user=player).select_related("course")

    # Get recent rounds for chart (ordered by date ascending)
    recent_rounds_list = list(
        all_user_rounds.order_by("date")[
            max(0, all_user_rounds.count() - RECENT_ROUNDS_DISPLAY) :
        ]
    )

    # Build chart data
    chart_dates, chart_scores, chart_handicaps = _build_player_chart_data(
        player, Round.objects.filter(user=player, pk__in=[r.id for r in recent_rounds_list])
    )

    # Calculate overall handicap
    handicap_result = calculate_handicap(player)
    handicap_index = handicap_result.index
    counting_ids = handicap_result.counting_round_ids

    # Get aggregate statistics
    stats = all_user_rounds.aggregate(
        low_score=Min("total_gross_score"),
        avg_score=Avg("total_gross_score"),
        best_diff=Min("differential"),
    )

    # Calculate form trend (last 3 rounds)
    recent_3_rounds = all_user_rounds.order_by("-date")[: RECENT_ROUNDS_TREND]
    trend_metric = _calculate_form_trend(recent_3_rounds, handicap_index)

    # Paginate all rounds for the rounds list
    paginator = Paginator(all_user_rounds.order_by("-date"), PAGINATION_PAGE_SIZE)
    page_number = request.GET.get("page")
    try:
        rounds_page = paginator.page(page_number)
    except PageNotAnInteger:
        rounds_page = paginator.page(1)
    except EmptyPage:
        rounds_page = paginator.page(paginator.num_pages)

    context = {
        "player": player,
        "rounds_page": rounds_page,
        "total_rounds": all_user_rounds.count(),
        "handicap_index": handicap_index,
        "counting_ids": counting_ids,
        "low_score": stats["low_score"],
        "avg_score": (round(stats["avg_score"], 1) if stats["avg_score"] else None),
        "best_diff": stats["best_diff"],
        "trend_metric": trend_metric,
        "chart_dates_json": json.dumps(chart_dates, cls=DjangoJSONEncoder),
        "chart_scores_json": json.dumps(chart_scores, cls=DjangoJSONEncoder),
        "chart_handicaps_json": json.dumps(chart_handicaps, cls=DjangoJSONEncoder),
    }

    return render(request, "scoring/player_profile.html", context)


@login_required
def enter_scorecard(request, course_id):
    """
    Create a new round and enter hole scores using an inline formset.
    """
    course = get_object_or_404(Course, pk=course_id)

    ScorecardFormSet = inlineformset_factory(
        Round,
        HoleScore,
        fields=("hole", "strokes", "putts"),
        extra=GOLF_HOLES,
        can_delete=False,
    )

    if request.method == "POST":
        new_round = Round(user=request.user, course=course)
        formset = ScorecardFormSet(request.POST, instance=new_round)

        if formset.is_valid():
            new_round.save()
            formset.save()
            return redirect("scoring:round_detail", round_id=new_round.id)
    else:
        formset = ScorecardFormSet()

    return render(
        request,
        "scoring/enter_scorecard.html",
        {"formset": formset, "course": course},
    )


def setup_course_holes(request, course_id):
    """
    Setup hole details (par, yardage) for a course's tee sets.
    """
    course = get_object_or_404(Course, pk=course_id)
    tee_sets = course.tee_sets.all()
    hole_range = range(1, GOLF_HOLES + 1)

    if request.method == "POST":
        for hole_number in hole_range:
            par_value = request.POST.get(f"par_{hole_number}")

            for tee in tee_sets:
                yardage_value = request.POST.get(f"yardage_{tee.id}_{hole_number}")

                Hole.objects.update_or_create(
                    tee_set=tee,
                    hole_number=hole_number,
                    defaults={"par": par_value, "yardage": yardage_value},
                )

        return redirect("scoring:course_detail", course_id=course.id)

    return render(
        request,
        "scoring/setup_holes_grid.html",
        {
            "course": course,
            "tee_sets": tee_sets,
            "hole_range": hole_range,
        },
    )


def load_tees(request):
    """
    AJAX endpoint to load tee sets for a given course.
    """
    course_id = request.GET.get("course")
    tees = TeeSet.objects.filter(course_id=course_id).order_by("color")

    return render(
        request,
        "scoring/tee_dropdown_list_options.html",
        {"tees": tees},
    )


def start_round(request):
    """
    Display list of courses to start a new round.
    """
    courses = Course.objects.all()

    return render(request, "scoring/start_round.html", {"courses": courses})


def leaderboard_view(request, slug):
    """
    Display leaderboard for a specific course.
    """
    course = get_object_or_404(Course, slug=slug)
    leaderboard_data = _build_course_leaderboard_data(course=course)

    context = {
        "leaderboard": leaderboard_data,
        "course": course,
        "all_courses": Course.objects.all(),
    }

    return render(request, "scoring/leaderboard.html", context)


def global_leaderboard(request):
    """
    Display global leaderboard across all courses with pagination.
    """
    leaderboard_data = _build_course_leaderboard_data(course=None)

    # Paginate leaderboard for large datasets
    paginator = Paginator(leaderboard_data, PAGINATION_PAGE_SIZE)
    page_number = request.GET.get("page")
    try:
        leaderboard_page = paginator.page(page_number)
    except PageNotAnInteger:
        leaderboard_page = paginator.page(1)
    except EmptyPage:
        leaderboard_page = paginator.page(paginator.num_pages)

    context = {
        "leaderboard_page": leaderboard_page,
        "all_courses": Course.objects.all(),
    }

    return render(request, "scoring/global_leaderboard.html", context)


@login_required
def add_round(request):
    """
    Create a new round via form submission.
    """
    if request.method == "POST":
        form = RoundForm(request.POST)
        if form.is_valid():
            new_round = form.save(commit=False)
            new_round.user = request.user
            new_round.save()

            return redirect("scoring:leaderboard")
    else:
        form = RoundForm()

    return render(request, "scoring/add_round.html", {"form": form})


@login_required
def enter_scores(request, round_id):
    """
    Enter hole-by-hole scores for a specific round.
    Only the round's owner can edit it.
    """
    round_obj = get_object_or_404(Round, pk=round_id, user=request.user)
    holes = Hole.objects.filter(course=round_obj.course).order_by("hole_number")

    # Fetch yardage for each hole in the round's tee set
    for hole in holes:
        hole.current_yardage = hole.yardages.filter(tee_set=round_obj.tee_set).first()

    if request.method == "POST":
        formset = HoleScoreFormSet(request.POST, instance=round_obj)
        if formset.is_valid():
            formset.save()
            return redirect("scoring:leaderboard")
    else:
        formset = HoleScoreFormSet(instance=round_obj)

    forms_with_holes = zip(formset, holes)

    return render(
        request,
        "scoring/enter_scores.html",
        {
            "forms_with_holes": forms_with_holes,
            "formset": formset,
            "round": round_obj,
        },
    )
