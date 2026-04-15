from django.forms import inlineformset_factory
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .models import Course, HoleScore, Round, TeeSet
from django.shortcuts import render, redirect, get_object_or_404
from .models import Course, TeeSet, Hole


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
        request, "scoring/enter_scorecard.html", {"formset": formset, "course": course}
    )


def setup_course_holes(request, course_id):
    course = get_object_or_404(Course, pk=course_id)
    tee_sets = course.tee_sets.all()
    hole_range = range(1, 19) # 1 through 18

    if request.method == "POST":
        for number in hole_range:
            # Get common data like Par (usually the same across tees)
            par_value = request.POST.get(f'par_{number}')
            
            for tee in tee_sets:
                yardage_value = request.POST.get(f'yardage_{tee.id}_{number}')
                
                # Update or create the hole record
                Hole.objects.update_or_create(
                    tee_set=tee,
                    hole_number=number,
                    defaults={'par': par_value, 'yardage': yardage_value}
                )
        return redirect('scoring:course_detail', course_id=course.id)

    return render(request, 'scoring/setup_holes_grid.html', {
        'course': course,
        'tee_sets': tee_sets,
        'hole_range': hole_range,
    })