from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.utils import timezone

from .models import HoleScore, Round, TeeSet

# ============================================================================
# Widget Configuration
# ============================================================================
# Centralized widget attributes to reduce repetition and improve maintainability

FORM_CONTROL_ATTRS = {"class": "form-control"}
NUMBER_INPUT_ATTRS = {**FORM_CONTROL_ATTRS, "min": 0}


# ============================================================================
# Formsets
# ============================================================================


class BaseHoleScoreFormSet(forms.BaseInlineFormSet):
    """Custom formset for HoleScore with cross-form validation."""

    def clean(self):
        """Validate the entire formset (all holes in the round)."""
        super().clean()

        if self.non_form_errors():
            return

        # Validate that putts don't exceed strokes for any hole
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False):
                strokes = form.cleaned_data.get("strokes")
                putts = form.cleaned_data.get("putts")

                if strokes and putts and putts > strokes:
                    raise ValidationError(
                        f"Putts ({putts}) cannot exceed strokes ({strokes}) on a hole."
                    )


class HoleScoreForm(forms.ModelForm):
    class Meta:
        model = HoleScore
        fields = ["strokes", "putts"]
        labels = {
            "strokes": "Strokes",
            "putts": "Putts",
        }


HoleScoreFormSet = inlineformset_factory(
    Round,
    HoleScore,
    form=HoleScoreForm,
    formset=BaseHoleScoreFormSet,
    fields=("strokes", "putts"),
    extra=18,
    can_delete=False,
)

# ============================================================================
# Forms
# ============================================================================


class HoleScoreForm(forms.ModelForm):
    """Form for entering individual hole scores (strokes and putts)."""

    class Meta:
        model = HoleScore
        fields = ["strokes", "putts"]
        labels = {
            "strokes": "Strokes",
            "putts": "Putts",
        }
        widgets = {
            "strokes": forms.NumberInput(
                attrs={**NUMBER_INPUT_ATTRS, "min": 1, "placeholder": "Strokes"}
            ),
            "putts": forms.NumberInput(
                attrs={**NUMBER_INPUT_ATTRS, "placeholder": "Putts"}
            ),
        }

    def clean(self):
        """Validate individual hole score."""
        cleaned_data = super().clean()
        strokes = cleaned_data.get("strokes")
        putts = cleaned_data.get("putts")

        if strokes and putts and putts > strokes:
            raise ValidationError("Putts cannot exceed the number of strokes.")

        return cleaned_data


class TeeSetForm(forms.ModelForm):
    """Form for creating/editing tee set information."""

    class Meta:
        model = TeeSet
        fields = ["color", "rating", "slope"]
        labels = {
            "color": "Tee Color",
            "rating": "Course Rating",
            "slope": "Slope Rating",
        }
        widgets = {
            "color": forms.TextInput(
                attrs={
                    **FORM_CONTROL_ATTRS,
                    "placeholder": "e.g., Black, Blue, White, Red",
                }
            ),
            "rating": forms.NumberInput(
                attrs={**FORM_CONTROL_ATTRS, "step": "0.1", "placeholder": "e.g., 72.5"}
            ),
            "slope": forms.NumberInput(
                attrs={**FORM_CONTROL_ATTRS, "placeholder": "e.g., 130"}
            ),
        }

    def clean(self):
        """Validate tee set data."""
        cleaned_data = super().clean()
        rating = cleaned_data.get("rating")
        slope = cleaned_data.get("slope")

        # Course rating should typically be between 60 and 80
        if rating and (rating < 50 or rating > 90):
            raise ValidationError(
                {"rating": "Course rating should typically be between 50 and 90."}
            )

        # Slope should be between 55 and 155
        if slope and (slope < 55 or slope > 155):
            raise ValidationError(
                {"slope": "Slope rating should be between 55 and 155."}
            )

        return cleaned_data


class RoundForm(forms.ModelForm):
    """Form for creating/editing a golf round."""

    class Meta:
        model = Round
        fields = ("course", "date", "total_gross_score", "completed_holes")
        labels = {
            "course": "Course",
            "date": "Date Played",
            "total_gross_score": "Total Gross Score",
            "completed_holes": "Holes Completed",
        }
        widgets = {
            "date": forms.DateTimeInput(
                attrs={**FORM_CONTROL_ATTRS, "type": "datetime-local"}
            ),
            "total_gross_score": forms.NumberInput(
                attrs={**NUMBER_INPUT_ATTRS, "min": 1, "placeholder": "Total score"}
            ),
            "completed_holes": forms.NumberInput(
                attrs={**NUMBER_INPUT_ATTRS, "min": 1, "max": 18, "placeholder": "0-18"}
            ),
        }

    def clean(self):
        """Validate round data."""
        cleaned_data = super().clean()
        date = cleaned_data.get("date")
        completed_holes = cleaned_data.get("completed_holes")
        total_score = cleaned_data.get("total_gross_score")

        # Validate date is not in the future
        if date and date > timezone.now():
            raise ValidationError({"date": "Round date cannot be in the future."})

        # Validate completed_holes is between 1 and 18
        if completed_holes and (completed_holes < 1 or completed_holes > 18):
            raise ValidationError(
                {"completed_holes": "Completed holes must be between 1 and 18."}
            )

        # Validate total_score is reasonable
        if total_score:
            min_expected = completed_holes * 1 if completed_holes else 1
            max_expected = completed_holes * 12 if completed_holes else 216
            if total_score < min_expected or total_score > max_expected:
                raise ValidationError(
                    {
                        "total_gross_score": f"Total score should be between {min_expected} and {max_expected} for {completed_holes} holes."
                    }
                )

        return cleaned_data
