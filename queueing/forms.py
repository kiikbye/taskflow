from django import forms

from .models import Batch


class BatchForm(forms.Form):
    title = forms.CharField(label="Топтама атауы", max_length=100, initial="Параллель есептеу")
    count = forms.IntegerField(label="Тапсырма саны", min_value=1, max_value=24, initial=9)
    duration = forms.IntegerField(label="Бір тапсырманың күту уақыты (сек)", min_value=1, max_value=12, initial=3)
    mode = forms.ChoiceField(label="Өңдеу режимі", choices=Batch.Mode.choices, initial=Batch.Mode.PARALLEL)
    fail_first = forms.BooleanField(label="Бірінші тапсырмаға сынақ қатесін енгізу", required=False)


class RenameForm(forms.ModelForm):
    class Meta:
        model = Batch
        fields = ("title",)
