import json
from datetime import date
from math import ceil, exp, floor, pi, sqrt

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Avg, Min, Prefetch
from django.forms import inlineformset_factory
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.generic import ListView

from .forms import HoleScoreFormSet, RoundForm
from .models import Course, Hole, HoleScore, Round, TeeSet
from .utils import calculate_handicap

UserModel = get_user_model()

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
VALID_BULK_HOLE_COUNTS = {9, 18}


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

    Args:
        player: User object
        recent_rounds: Iterable of recent Round objects (ordered ascending by date)

    Returns:
        tuple: (chart_dates, chart_scores, chart_handicaps)
    """
    chart_dates = []
    chart_scores = []
    chart_handicaps = []

    for round_obj in recent_rounds:
        chart_dates.append(round_obj.date.strftime("%b %d, %Y"))

        # Add score if available
        if round_obj.total_gross_score is not None:
            chart_scores.append(round_obj.total_gross_score)
        else:
            chart_scores.append(None)

        history_up_to = Round.objects.filter(user=player, date__lte=round_obj.date)
        h_index = calculate_handicap(history_up_to).index
        if h_index is not None and h_index != HANDICAP_DEFAULT_DISPLAY:
            chart_handicaps.append(float(h_index))
        else:
            chart_handicaps.append(None)

    return chart_dates, chart_scores, chart_handicaps


def _build_score_distribution_data(scores):
    """Build histogram and normal-distribution data for a player's scores.

    The normal curve is scaled to the number of rounds, allowing it to share
    the count axis with the score-frequency bars.
    """
    if not scores:
        return [], [], [], [], None, None

    mean = sum(scores) / len(scores)
    variance = sum((score - mean) ** 2 for score in scores) / len(scores)
    standard_deviation = sqrt(variance)

    # Include enough range on either side of the average to make the shape of
    # the curve readable, while retaining every score in the histogram.
    curve_padding = max(3, standard_deviation * 3)
    low_score = min(min(scores), floor(mean - curve_padding))
    high_score = max(max(scores), ceil(mean + curve_padding))
    labels = list(range(low_score, high_score + 1))
    frequencies = [scores.count(score) for score in labels]

    if standard_deviation == 0:
        curve = [len(scores) if score == round(mean) else 0 for score in labels]
    else:
        scale = len(scores)
        curve = [
            round(
                scale
                * (1 / (standard_deviation * sqrt(2 * pi)))
                * exp(-0.5 * ((score - mean) / standard_deviation) ** 2),
                2,
            )
            for score in labels
        ]

    deviations = [
        {
            "standard_deviations": multiplier,
            "score": round(mean + direction * multiplier * standard_deviation, 1),
        }
        for multiplier in range(1, 4)
        for direction in (-1, 1)
    ]
    return (
        labels,
        frequencies,
        curve,
        deviations,
        round(mean, 1),
        round(standard_deviation, 1),
    )


def _calculate_form_trend(recent_rounds, handicap_index):
    """Calculate form trend (average of recent rounds vs overall
    handicap).

    Args:
        recent_rounds: Iterable of recent Round objects
        handicap_index: Player's current handicap index (float or None)

    Returns:
        float or None: Trend metric or None if not enough rounds

    """
    if len(recent_rounds) < RECENT_ROUNDS_TREND:
        return None

    valid_differentials = [
        float(r.differential) for r in recent_rounds if r.differential is not None
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
    buddies = UserModel.objects.filter(id__in=player_ids).prefetch_related(
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
            recent_scores = [
                {"round_id": r.id, "score": r.total_score, "date": r.date}
                for r in recent_rounds
            ]
        else:
            recent_rounds = list(buddy.round_set.all())[:RECENT_GLOBAL_ROUNDS]
            recent_scores = [
                {
                    "round_id": r.id,
                    "score": r.total_score,
                    "course": r.course.name,
                    "date": r.date,
                }
                for r in recent_rounds
            ]

        leaderboard_data.append(
            _build_leaderboard_entry(buddy, handicap, recent_scores)
        )

    # Sort by handicap (lowest to highest)
    leaderboard_data.sort(key=lambda x: _get_numeric_handicap(x["handicap"]))

    return leaderboard_data


def _parse_positive_int(value):
    if value in (None, ""):
        return None

    try:
        parsed_value = int(value)
    except (TypeError, ValueError):
        return None

    return parsed_value if parsed_value > 0 else None


def _create_total_score_round(user, course, tee_set, played_on, score, holes_played):
    round_obj = Round.objects.create(
        user=user,
        course=course,
        tee_set=tee_set,
        date=played_on,
        total_gross_score=score,
        completed_holes=holes_played,
    )
    round_obj.update_differential()
    round_obj.save(
        update_fields=["total_gross_score", "completed_holes", "differential"]
    )
    return round_obj


def _create_hole_score_round(user, course, tee_set, played_on, scores):
    round_obj = Round.objects.create(
        user=user,
        course=course,
        tee_set=tee_set,
        date=played_on,
        total_gross_score=sum(scores),
        completed_holes=len(scores),
    )
    holes = list(tee_set.holes.order_by("hole_number")[: len(scores)])
    HoleScore.objects.bulk_create(
        [
            HoleScore(round=round_obj, hole=hole, strokes=score)
            for hole, score in zip(holes, scores)
        ]
    )
    round_obj.update_differential()
    round_obj.save(
        update_fields=["total_gross_score", "completed_holes", "differential"]
    )
    return round_obj


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
    ordering = "-date"
    paginate_by = PAGINATION_PAGE_SIZE


def round_detail(request, round_id):
    """
    Display details for a specific round.
    """
    round_obj = get_object_or_404(
        Round.objects.select_related("user", "course", "tee_set"), pk=round_id
    )
    hole_scores = list(
        round_obj.scores.select_related("hole").order_by("hole__hole_number")
    )

    context = {
        "round": round_obj,
        "hole_scores": hole_scores,
        "total": round_obj.total_score,
        "relative_to_par": round_obj.total_score - round_obj.total_par,
        "total_putts": sum(score.putts for score in hole_scores),
    }

    return render(request, "scoring/round_detail.html", context)


def player_profile(request, username):
    """
    Display player profile with stats, recent rounds, and trend charts.

    Optimized with efficient queries and pagination for large datasets.
    """
    player = get_object_or_404(UserModel, username=username)
    all_user_rounds = Round.objects.filter(user=player).select_related("course")

    # Paginator caches the queryset count, which we can reuse for both the
    # profile summary and the recent-round chart slice.
    paginator = Paginator(all_user_rounds.order_by("-date"), PAGINATION_PAGE_SIZE)
    total_rounds = paginator.count

    # Get recent rounds for chart (ordered by date ascending)
    recent_rounds_list = list(
        all_user_rounds.order_by("date")[max(0, total_rounds - RECENT_ROUNDS_DISPLAY) :]
    )

    # Build chart data
    chart_dates, chart_scores, chart_handicaps = _build_player_chart_data(
        player, recent_rounds_list
    )

    distribution_scores = list(
        all_user_rounds.filter(completed_holes=9, total_gross_score__gt=0).values_list(
            "total_gross_score", flat=True
        )
    )
    (
        score_distribution_labels,
        score_distribution_counts,
        score_distribution_curve,
        score_distribution_deviations,
        score_distribution_mean,
        score_distribution_stddev,
    ) = _build_score_distribution_data(distribution_scores)

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
    recent_3_rounds = list(all_user_rounds.order_by("-date")[:RECENT_ROUNDS_TREND])
    trend_metric = _calculate_form_trend(recent_3_rounds, handicap_index)

    # Paginate all rounds for the rounds list
    page_number = request.GET.get("page")
    try:
        rounds_page = paginator.page(page_number)
    except PageNotAnInteger:
        rounds_page = paginator.page(1)
    except EmptyPage:
        rounds_page = paginator.page(paginator.num_pages)

    context = {
        "player": player,
        "rounds": rounds_page,
        "rounds_page": rounds_page,
        "total_rounds": total_rounds,
        "handicap_index": handicap_index,
        "handicap_rounds_considered": handicap_result.rounds_considered,
        "handicap_rounds_used": handicap_result.rounds_used,
        "counting_ids": counting_ids,
        "low_score": stats["low_score"],
        "avg_score": (round(stats["avg_score"], 1) if stats["avg_score"] else None),
        "best_diff": stats["best_diff"],
        "trend_metric": trend_metric,
        "chart_dates_json": json.dumps(chart_dates, cls=DjangoJSONEncoder),
        "chart_scores_json": json.dumps(chart_scores, cls=DjangoJSONEncoder),
        "chart_handicaps_json": json.dumps(chart_handicaps, cls=DjangoJSONEncoder),
        "score_distribution_labels_json": json.dumps(
            score_distribution_labels, cls=DjangoJSONEncoder
        ),
        "score_distribution_counts_json": json.dumps(
            score_distribution_counts, cls=DjangoJSONEncoder
        ),
        "score_distribution_curve_json": json.dumps(
            score_distribution_curve, cls=DjangoJSONEncoder
        ),
        "score_distribution_deviations_json": json.dumps(
            score_distribution_deviations, cls=DjangoJSONEncoder
        ),
        "score_distribution_round_count": len(distribution_scores),
        "score_distribution_mean": score_distribution_mean,
        "score_distribution_stddev": score_distribution_stddev,
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
    tee_sets = course.tees.all()
    hole_range = range(1, GOLF_HOLES + 1)

    if request.method == "POST":
        hole_data = []
        for hole_number in hole_range:
            par_value = _parse_positive_int(request.POST.get(f"par_{hole_number}"))
            if par_value not in {3, 4, 5}:
                messages.error(request, f"Hole {hole_number} par must be 3, 4, or 5.")
                return render(
                    request,
                    "scoring/setup_holes_grid.html",
                    {"course": course, "tee_sets": tee_sets, "hole_range": hole_range},
                )

            for tee in tee_sets:
                yardage_value = _parse_positive_int(
                    request.POST.get(f"yardage_{tee.id}_{hole_number}")
                )
                if yardage_value is None:
                    messages.error(
                        request,
                        f"Enter a positive yardage for {tee.color}, hole {hole_number}.",
                    )
                    return render(
                        request,
                        "scoring/setup_holes_grid.html",
                        {
                            "course": course,
                            "tee_sets": tee_sets,
                            "hole_range": hole_range,
                        },
                    )
                hole_data.append((tee, hole_number, par_value, yardage_value))

        for tee, hole_number, par_value, yardage_value in hole_data:
            Hole.objects.update_or_create(
                tee_set=tee,
                hole_number=hole_number,
                defaults={"par": par_value, "yardage": yardage_value},
            )

        return redirect("scoring:setup_holes", course_id=course.id)

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


def daily_scores_today(request):
    """Redirect to the daily scores page for a selected date, defaulting to today."""
    date_value = request.GET.get("date")
    selected_date = parse_date(date_value) if date_value else timezone.localdate()
    if selected_date is None:
        messages.error(request, "Please select a valid date.")
        selected_date = timezone.localdate()

    return redirect(
        "scoring:daily_scores",
        year=selected_date.year,
        month=selected_date.month,
        day=selected_date.day,
    )


def daily_scores(request, year, month, day):
    """Show only the rounds played on the requested calendar date."""
    try:
        selected_date = date(year, month, day)
    except ValueError as exc:
        raise Http404("Invalid score date") from exc

    rounds = (
        Round.objects.filter(date=selected_date)
        .select_related("user", "course", "tee_set")
        .order_by(
            "total_gross_score",
            "user__first_name",
            "user__username",
            "course__name",
        )
    )
    return render(
        request,
        "scoring/daily_scores.html",
        {"rounds": rounds, "selected_date": selected_date},
    )


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
def bulk_add_rounds(request):
    """
    Create rounds for multiple players on the same course, tee set, and date.
    """
    courses = Course.objects.prefetch_related("tees__holes").all()
    tee_sets = TeeSet.objects.select_related("course").prefetch_related("holes")
    players = UserModel.objects.order_by("first_name", "last_name", "username")

    context = {
        "courses": courses,
        "tee_sets": tee_sets,
        "players": players,
        "hole_range": range(1, GOLF_HOLES + 1),
    }

    if request.method != "POST":
        return render(request, "scoring/bulk_add_rounds.html", context)

    course = Course.objects.filter(pk=request.POST.get("course")).first()
    tee_set = TeeSet.objects.filter(pk=request.POST.get("tee_set")).first()
    played_on_raw = request.POST.get("date")
    played_on = parse_date(played_on_raw) if played_on_raw else None
    entry_mode = request.POST.get("entry_mode")
    selected_player_ids = request.POST.getlist("players")

    context.update(
        {
            "selected_course_id": request.POST.get("course"),
            "selected_tee_set_id": request.POST.get("tee_set"),
            "selected_date": played_on_raw,
            "selected_entry_mode": entry_mode,
            "selected_player_ids": selected_player_ids,
            "posted_data": request.POST,
        }
    )

    errors = []
    rounds_to_create = []

    if not course:
        errors.append("Choose a course.")
    if not tee_set:
        errors.append("Choose a tee color.")
    elif course and tee_set.course_id != course.id:
        errors.append("The selected tee color does not belong to that course.")
    if entry_mode not in {"total", "holes"}:
        errors.append("Choose total score or hole-by-hole entry.")
    if played_on_raw and played_on is None:
        errors.append("Enter a valid date.")
    if not selected_player_ids:
        errors.append("Choose at least one player.")

    selected_players = list(UserModel.objects.filter(id__in=selected_player_ids))
    selected_players_by_id = {str(player.id): player for player in selected_players}

    if tee_set:
        available_holes = list(tee_set.holes.order_by("hole_number"))
        if len(available_holes) < 9:
            errors.append("The selected tee color needs at least 9 holes set up first.")

    for player_id in selected_player_ids:
        player = selected_players_by_id.get(player_id)
        if not player:
            errors.append("One of the selected players could not be found.")
            continue

        player_name = player.get_full_name() or player.username

        if entry_mode == "total":
            score = _parse_positive_int(request.POST.get(f"total_score_{player_id}"))
            holes_played = _parse_positive_int(
                request.POST.get(f"holes_played_{player_id}")
            )

            if score is None:
                errors.append(f"Enter a total score for {player_name}.")
                continue
            if holes_played not in VALID_BULK_HOLE_COUNTS:
                errors.append(f"Choose 9 or 18 holes for {player_name}.")
                continue

            rounds_to_create.append(("total", player, score, holes_played))

        elif entry_mode == "holes":
            scores = [
                _parse_positive_int(request.POST.get(f"hole_{player_id}_{hole_number}"))
                for hole_number in range(1, GOLF_HOLES + 1)
            ]
            scores = [score for score in scores if score is not None]

            if len(scores) not in VALID_BULK_HOLE_COUNTS:
                errors.append(f"Enter exactly 9 or 18 hole scores for {player_name}.")
                continue

            rounds_to_create.append(("holes", player, scores, len(scores)))

    if errors:
        for error in errors:
            messages.error(request, error)
        return render(request, "scoring/bulk_add_rounds.html", context)

    with transaction.atomic():
        for mode, player, score_data, holes_played in rounds_to_create:
            if mode == "total":
                _create_total_score_round(
                    player, course, tee_set, played_on, score_data, holes_played
                )
            else:
                _create_hole_score_round(player, course, tee_set, played_on, score_data)

    messages.success(request, f"Posted {len(rounds_to_create)} round(s).")
    return redirect("scoring:round_list")


@login_required
def enter_scores(request, round_id):
    """
    Enter hole-by-hole scores for a specific round.
    Only the round's owner can edit it.
    """
    round_obj = get_object_or_404(Round, pk=round_id, user=request.user)
    holes = (
        round_obj.tee_set.holes.order_by("hole_number")
        if round_obj.tee_set_id
        else Hole.objects.none()
    )

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
