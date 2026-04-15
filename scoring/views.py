from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.shortcuts import redirect
from django.forms import inlineformset_factory
from .models import Round, HoleScore, Course


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
    course = Course.objects.get(pk=course_id)
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
        request, "scoring/enter_scorecard.html", {"formset": formset, "course": course}
    )
