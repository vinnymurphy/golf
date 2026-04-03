from django.http import HttpResponse

def index(request):
    return HttpResponse("Welcome to the Golf Scoring Dashboard!")

def round_detail(request, round_id):
    return HttpResponse(f"Showing details for Round ID: {round_id}")

def leaderboard(request):
    return HttpResponse("Global Golf Leaderboard")
