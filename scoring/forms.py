from django import forms
from django.forms import inlineformset_factory

from .models import HoleScore, Round, TeeSet

# This defines how a "Collection" of HoleScores relates to a Round
HoleScoreFormSet = inlineformset_factory(
    Round,
    HoleScore,
    fields=["strokes", "putts"],
    extra=18,  # Pre-fills 18 holes
    can_delete=False,  # Prevents accidental deletion of holes during entry
)


class HoleScoreForm(forms.ModelForm):
    class Meta:
        model = HoleScore
        fields = ["strokes", "putts"]
        widgets = {
            "strokes": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "putts": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
        }


class TeeSetForm(forms.ModelForm):
    class Meta:
        model = TeeSet
        fields = ["color", "rating", "slope"]
        widgets = {
            "color": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g. Black"}
            ),
            "rating": forms.NumberInput(attrs={"step": "0.1", "class": "form-control"}),
            "slope": forms.NumberInput(attrs={"class": "form-control"}),
        }


class RoundForm(forms.ModelForm):
    class Meta:
        model = Round
        # We define fields as a tuple here to prevent the 'list' TypeError you saw earlier
        fields = ("course", "date", "total_gross_score", "completed_holes")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # We use .get() to avoid crashing if the field is missing during a system check
        if self.fields.get("total_gross_score"):
            self.fields["total_gross_score"].label = "Total Gross Score"
