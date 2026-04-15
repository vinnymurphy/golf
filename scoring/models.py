from django.db import models
from django.contrib.auth.models import User


class Course(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.name


class Hole(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="holes")
    hole_number = models.IntegerField()
    par = models.IntegerField(default=4)
    yardage = models.IntegerField(blank=True, null=True)

    class Meta:
        ordering = ["hole_number"]


class Round(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    date_played = models.DateTimeField(auto_now_add=True)

    @property
    def total_score(self):
        return (
            self.scores.aggregate(models.Sum("strokes"))["strokes__sum"]
            if self.scores.exists()
            else 0
        )

    @property
    def total_par(self):
        return (
            self.scores.aggregate(models.Sum("hole__par"))["hole__par__sum"]
            if self.scores.exists()
            else 0
        )

    def __str__(self):
        return f"{self.user.username} at {self.course.name} ({self.date_played.date()})"


class HoleScore(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="scores")
    hole = models.ForeignKey(Hole, on_delete=models.CASCADE)
    strokes = models.IntegerField()
    putts = models.IntegerField(default=0)

    def __str__(self):
        return f"Hole {self.hole.hole_number}: {self.strokes} strokes"
