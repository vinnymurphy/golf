from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


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
    tee_set = models.ForeignKey(TeeSet, on_delete=models.CASCADE, related_name="holes", null=True, blank=True)
    hole_number = models.IntegerField()
    par = models.IntegerField(default=4)
    yardage = models.IntegerField(blank=True, null=True)

    class Meta:
        ordering = ["hole_number"]


class Round(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey("Course", on_delete=models.CASCADE)
    # Make sure these names are EXACTLY as written here:
    date = models.DateField(default=timezone.now) 
    total_gross_score = models.IntegerField(default=0)
    completed_holes = models.IntegerField(default=18)
    HOLE_CHOICES = [(9, "9 Holes"), (18, "18 Holes")]
    holes_played = models.IntegerField(choices=HOLE_CHOICES, default=18)

    date_played = models.DateField(default=timezone.now)
    # Ensure this matches the 'scores' name in your Choice list
    scores = models.IntegerField()
    differential = models.DecimalField(max_digits=5, decimal_places=2, editable=False)
    external_url = models.URLField(max_length=500, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.differential and self.tee_set:
            # WHS 9-hole math: (Score - 9-hole Rating) * 113 / 9-hole Slope
            # Note: This assumes your TeeSet stores the 9-hole rating/slope
            # if that's what is being played.

            raw_diff = (float(self.scores) - float(self.tee_set.rating)) * (
                113 / self.tee_set.slope
            )

            # If it's a 9-hole round, the differential is handled
            # specifically by the handicap index (often doubled or combined)
            # For now, we store the raw differential of the play.
            self.differential = raw_diff

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
    round = models.ForeignKey(
        Round, on_delete=models.CASCADE, related_name="hole_scores"
    )
    hole = models.ForeignKey(Hole, on_delete=models.CASCADE)
    strokes = models.IntegerField()
    putts = models.IntegerField(default=0)

    def __str__(self):
        return f"Hole {self.hole.hole_number}: {self.strokes} strokes"
