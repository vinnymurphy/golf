from django.contrib import admin

from .models import Course, Hole, HoleScore, Round, TeeSet


# This lets you edit Tee Sets while looking at a Course
class TeeSetInline(admin.TabularInline):
    model = TeeSet
    extra = 1


# This lets you edit Holes while looking at a Tee Set
class HoleInline(admin.TabularInline):
    model = Hole
    extra = 18  # Pre-populate 18 rows for convenience
    fields = ("number", "handicap", "par")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("name", "location")
    search_fields = ("name", "location")
    inlines = [TeeSetInline]


@admin.register(TeeSet)
class TeeSetAdmin(admin.ModelAdmin):
    list_display = ("course", "color", "rating", "slope")
    list_filter = ("course", "color")
    ordering = ("course", "color")
    inlines = [HoleInline]


@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    # Make sure 'tee_set' is NOT in this list
    list_display = ("date", "course", "total_gross_score", "completed_holes")
    list_filter = ("course", "date")
    readonly_fields = ("total_gross_score", "completed_holes")
    date_hierarchy = "date"


@admin.register(Hole)
class HoleAdmin(admin.ModelAdmin):
    list_display = ("tee_set", "number", "par", "handicap")
    list_filter = ("tee_set__course", "par")
    ordering = ("tee_set", "number")


@admin.register(HoleScore)
class HoleScoreAdmin(admin.ModelAdmin):
    list_display = ("round", "hole", "gross_score")
    list_filter = ("round__date", "round__course")
    search_fields = ("round__course__name",)
