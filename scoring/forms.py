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
        # fields = ["course", "tee_set", "holes_played", "date_played", "scores"]
        fields = ["course",  "holes_played", "date_played", "scores"]
        widgets = {
            "date_played": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "course": forms.Select(attrs={"class": "form-select"}),
            # "tee_set": forms.Select(attrs={"class": "form-select"}),
            "holes_played": forms.Select(attrs={"class": "form-select"}),
            "scores": forms.NumberInput(
                attrs={"class": "form-control", "placeholder": "Gross Score"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Standardizing the labels for your buddies
        self.fields["tee_set"].label = "Tee Color / Set"
        self.fields["scores"].label = "Total Gross Score"
