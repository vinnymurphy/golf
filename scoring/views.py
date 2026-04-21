from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.forms import inlineformset_factory
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import RoundForm
from .models import Course, Hole, HoleScore, Round, TeeSet
from .utils import calculate_handicap

from django.forms import inlineformset_factory

HoleScoreFormSet = inlineformset_factory(
    Round, 
    HoleScore, 
    fields=["strokes", "putts"], 
    extra=18
)

def index(request):
    return HttpResponse("Welcome to the Golf Scoring Dashboard!")


def leaderboard(request):
    return HttpResponse("Global Golf Leaderboard")


def round_detail(request, round_id):
    # Fetch the specific round or return a 404 error if it doesn't exist
    round_obj = get_object_or_404(Round, pk=round_id)

    # We pass the round object to a template
    context = {
        "round": round_obj,
        "total": round_obj.total_score,
        "relative_to_par": round_obj.total_score - round_obj.total_par,
    }
    return render(request, "scoring/round_detail.html", context)


def enter_scorecard(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    # This creates a formset linked specifically between Round and HoleScore
    ScorecardFormSet = inlineformset_factory(
        Round,
        HoleScore,
        fields=("hole", "strokes", "putts"),
        extra=18,
        can_delete=False,
    )

    if request.method == "POST":
        # 1. Create the Round object
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
    course = get_object_or_404(Course, pk=course_id)
    tee_sets = course.tee_sets.all()
    hole_range = range(1, 19)  # 1 through 18

    if request.method == "POST":
        for number in hole_range:
            # Get common data like Par (usually the same across tees)
            par_value = request.POST.get(f"par_{number}")

            for tee in tee_sets:
                yardage_value = request.POST.get(f"yardage_{tee.id}_{number}")

                # Update or create the hole record
                Hole.objects.update_or_create(
                    tee_set=tee,
                    hole_number=number,
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
    course_id = request.GET.get("course")
    tees = TeeSet.objects.filter(course_id=course_id).order_by("color")
    return render(request, "scoring/tee_dropdown_list_options.html", {"tees": tees})


def start_round(request):
    courses = Course.objects.all()
    return render(request, "scoring/start_round.html", {"courses": courses})


def leaderboard_view(request):
    buddies = User.objects.all()
    leaderboard_data = []

    for buddy in buddies:
        recent_rounds = Round.objects.filter(user=buddy).order_by("-date_played")[:5]

        handicap = calculate_handicap(buddy)

        leaderboard_data.append(
            {
                "user": buddy,
                "handicap": handicap if handicap is not None else "N/A",
                # Ensure this matches your field name (the error says 'scores')
                "recent_scores": [r.scores for r in recent_rounds],
                "sort_val": handicap if handicap is not None else 99.9,
            }
        )

    leaderboard_data.sort(key=lambda x: x["sort_val"])
    return render(
        request, "scoring/leaderboard.html", {"leaderboard": leaderboard_data}
    )


@login_required
def add_round(request):
    if request.method == "POST":
        form = RoundForm(request.POST)
        if form.is_valid():
            # commit=False gives us a model instance before it hits the DB
            new_round = form.save(commit=False)
            # Assign the current logged-in buddy
            new_round.user = request.user
            # Now save to DB, triggering your custom save() math for the differential
            new_round.save()
            return redirect("scoring:leaderboard")
    else:
        form = RoundForm()

    return render(request, "scoring/add_round.html", {"form": form})


def enter_scores(request, round_id):
    round_obj = get_object_or_404(Round, pk=round_id)
    # Get all holes for this course, but select the specific tee data
    # This assumes your Hole model has a related TeeSet or a Yardage model
    holes = Hole.objects.filter(course=round_obj.course).order_by("hole_number")

    # Get yardage for the specific tee chosen for this round
    # You might need to adjust this depending on if yardage is on the Hole or a separate model
    for hole in holes:
        # Fetch the specific yardage for the Round's tee_set
        hole.current_yardage = hole.yardages.filter(tee_set=round_obj.tee_set).first()

    if request.method == "POST":
        formset = HoleScoreFormSet(request.POST, instance=round_obj)
        if formset.is_valid():
            formset.save()
            return redirect("scoring:leaderboard")
    else:
        formset = HoleScoreFormSet(instance=round_obj)

    # Zip them so they line up in the template
    forms_with_holes = zip(formset, holes)

    return render(
        request,
        "scoring/enter_scores.html",
        {"forms_with_holes": forms_with_holes, "formset": formset, "round": round_obj},
    )
