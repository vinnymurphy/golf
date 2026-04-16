from django.contrib.auth.models import User
from django.db import models


class Course(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=100, default="Marion, MA")

    def __str__(self):
        return self.name


class TeeSet(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="tees")
    name = models.CharField(max_length=50)
    color = models.CharField(
        max_length=20, help_text="e.g., Blue, White, Gold, Black, or Combo"
    )
    rating = models.DecimalField(
        max_digits=4, decimal_places=1, help_text="USGA Course Rating (e.g., 71.2)"
    )
    slope = models.IntegerField(help_text="USGA Slope Rating (usually 55-155)")

    def __str__(self):
        return f"{self.course.name} - {self.color}"


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
    differential = models.DecimalField(max_digits=5, decimal_places=2, editable=False)

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

    def save(self, *args, **kwargs):
        # We need the Slope and Rating from the TeeSet to do the math.
        # This assumes your Round model has a 'tee_set' foreign key.
        if not self.differential:
            # Formula: (Score - Rating) * 113 / Slope
            # We use float() because Decimal and float don't always mix well in Python math
            diff = (float(self.total_score) - float(self.tee_set.rating)) * (
                113 / self.tee_set.slope
            )
            self.differential = diff
        super().save(*args, **kwargs)


class HoleScore(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="scores")
    hole = models.ForeignKey(Hole, on_delete=models.CASCADE)
    strokes = models.IntegerField()
    putts = models.IntegerField(default=0)

    def __str__(self):
        return f"Hole {self.hole.hole_number}: {self.strokes} strokes"
