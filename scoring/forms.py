from django import forms
from django.forms import inlineformset_factory
from .models import Round, HoleScore, TeeSet

# This defines how a "Collection" of HoleScores relates to a Round
HoleScoreFormSet = inlineformset_factory(
    Round,
    HoleScore,
    fields=["strokes", "putts"],
    extra=18,           # Pre-fills 18 holes
    can_delete=False,   # Prevents accidental deletion of holes during entry
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
        # Ensure this is a simple list of strings. 
        # Check for any accidental nested brackets like [["course"]]
        fields = ["course"] 

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Leave all custom logic commented out until the migration passes