from django import forms

from .models import HoleScore, TeeSet


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
