from django.contrib import admin
from .models import Course, Hole, Round, HoleScore

admin.site.register(Course)
admin.site.register(Hole)
admin.site.register(Round)
admin.site.register(HoleScore)
