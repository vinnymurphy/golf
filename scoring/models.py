from django.db import models

class Round(models.Model):
    player_name = models.CharField(max_length=100)
    course_name = models.CharField(max_length=100)
    date_played = models.DateField(auto_now_add=True)
    total_score = models.IntegerField()

    def __str__(self):
        return f"{self.player_name} - {self.course_name}: {self.total_score}"

