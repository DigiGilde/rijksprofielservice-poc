from django import forms
from django.contrib.auth import get_user_model

from .models import UserProfile

User = get_user_model()


class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(label="Voornaam", required=False)
    last_name = forms.CharField(label="Achternaam", required=False)

    class Meta:
        model = UserProfile
        fields = ["telefoon", "functie", "organisatie"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user_id:
            self.fields["first_name"].initial = self.instance.user.first_name
            self.fields["last_name"].initial = self.instance.user.last_name

    def save(self, commit=True):
        profile = super().save(commit=commit)
        user = profile.user
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        if commit:
            user.save(update_fields=["first_name", "last_name"])
        return profile


class AvatarForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ["avatar"]
