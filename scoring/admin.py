from django.contrib import admin
from .models import Course, TeeSet, Hole, Round, HoleScore


# This lets you edit Tee Sets while looking at a Course
class TeeSetInline(admin.TabularInline):
    model = TeeSet
    extra = 1


# This lets you edit Holes while looking at a Tee Set
class HoleInline(admin.TabularInline):
    model = Hole
    extra = 18  # Pre-populate 18 rows for convenience


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("name", "location")
    inlines = [TeeSetInline]


@admin.register(TeeSet)
class TeeSetAdmin(admin.ModelAdmin):
    list_display = ("course", "color", "rating", "slope")
    list_filter = ("course", "color")
    inlines = [HoleInline]


# @admin.register(Round)
# class RoundAdmin(admin.ModelAdmin):
#     list_display = ("date", "user", "course", "total_gross_score", "completed_holes")
#     list_filter = ("course", "user", "date")
admin.site.register(Round)

# Register the rest simply
admin.site.register(Hole)
admin.site.register(HoleScore)
