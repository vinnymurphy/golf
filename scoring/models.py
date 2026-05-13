from decimal import Decimal

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Course(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=100, default="Marion, MA")
    slug = models.SlugField(unique=True, blank=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.name.lower().replace(" ", "-")
        super().save(*args, **kwargs)


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
    tee_set = models.ForeignKey(
        TeeSet, on_delete=models.CASCADE, related_name="holes", null=True, blank=True
    )
    hole_number = models.IntegerField()
    par = models.IntegerField(default=4)
    yardage = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return f"{self.tee_set}, {self.hole_number}"

    class Meta:
        ordering = ["hole_number"]


class Round(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    course = models.ForeignKey("Course", on_delete=models.CASCADE)
    date = models.DateField(default=timezone.now)
    total_gross_score = models.IntegerField(default=0)
    completed_holes = models.IntegerField(default=18)
    # We allow null=True here so the import can save before calculating the diff
    differential = models.DecimalField(
        max_digits=5, decimal_places=2, editable=False, null=True, blank=True
    )
    external_url = models.URLField(max_length=500, null=True, blank=True)

    @property
    def total_score(self):
        # Use 'scores' because that is the related_name we set in the migration
        if self.scores.exists():
            return self.scores.aggregate(models.Sum("strokes"))[
                "strokes__sum"
            ] or Decimal("0.00")
        return self.total_gross_score

    @property
    def total_par(self):
        # 1. If we have individual hole scores, use those (most accurate)
        if self.scores.exists():
            return sum(score.hole.par for score in self.scores.all())

        # 2. Fallback for summary-only imports (where total_par was showing 68)
        tee = self.course.tees.first()
        if tee:
            # Sort holes by number and slice based on completed_holes (e.g., 9)
            holes = tee.holes.all().order_by("hole_number")[: self.completed_holes]
            return sum(h.par for h in holes)

        return 0

    def update_differential(self):
        all_scores = self.scores.all()

        # Scenario A: We have individual HoleScores
        if all_scores.exists():
            gross = Decimal(str(sum(s.strokes for s in all_scores)))
            self.total_gross_score = int(gross)
            tee = all_scores.first().hole.tee_set

        # Scenario B: No HoleScores (CSV Import Fallback)
        else:
            gross = Decimal(str(self.total_gross_score))
            # Find the TeeSet associated with this course.
            # We use .first() as a safe default for historical data.
            tee = self.course.tees.first()

        if not tee or gross == 0:
            return None

        try:
            # Use full 18-hole ratings for both scenarios
            rating = Decimal(str(tee.rating))
            slope = Decimal(str(tee.slope))

            if self.completed_holes == 9:
                # 1. Double the score to see the 18-hole "pace"
                # 2. Calculate the 18-hole differential
                # 3. Divide by 2 to get the 9-hole value
                full_diff = (Decimal("113") / slope) * ((gross * 2) - rating)
                self.differential = full_diff / 2
            else:
                # Standard 18-hole calculation
                self.differential = (Decimal("113") / slope) * (gross - rating)

            return self.differential
        except Exception:
            return None

    def __str__(self):
        return f"{self.user.username} at {self.course.name} ({self.date})"

    def save(self, *args, **kwargs):
        # On updates (when the round already exists in the DB),
        # we can try to recalculate the differential.
        if self.pk:
            self.update_differential()

        # If it's a new round and differential is still null,
        # default to 0.0 so the DB doesn't complain
        if self.differential is None:
            self.differential = Decimal("0.00")

        super().save(*args, **kwargs)


class HoleScore(models.Model):
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="scores")
    hole = models.ForeignKey(Hole, on_delete=models.CASCADE)
    strokes = models.IntegerField()
    putts = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.round.user.first_name} - Hole {self.hole.hole_number}: {self.strokes} strokes"
