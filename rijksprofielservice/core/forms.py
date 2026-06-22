from django import forms
from django.contrib.auth import get_user_model
from oauth2_provider.models import get_application_model

from .models import FIELD_CHOICES, Application, UserProfile

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


class ApplicationCreateForm(forms.Form):
    naam = forms.CharField(label="Naam", max_length=128)
    client_id = forms.CharField(label="Client ID", max_length=128)
    beschrijving = forms.CharField(label="Beschrijving", widget=forms.Textarea(attrs={"rows": 3}), required=False)
    redirect_uri = forms.URLField(label="Redirect URI", assume_scheme="https")
    requested_fields = forms.MultipleChoiceField(
        label="Gevraagde velden",
        choices=FIELD_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    is_approved = forms.BooleanField(label="Direct goedgekeurd", required=False, initial=True)

    def clean_client_id(self):
        client_id = self.cleaned_data["client_id"].strip()
        if not client_id:
            raise forms.ValidationError("Client ID is verplicht.")
        DotApp = get_application_model()
        if DotApp.objects.filter(client_id=client_id).exists():
            raise forms.ValidationError("Deze client_id is al in gebruik.")
        if DotApp.objects.filter(client_id=f"{client_id}-m2m").exists():
            raise forms.ValidationError("De bijbehorende -m2m client_id is al in gebruik.")
        if Application.objects.filter(client_id=client_id).exists():
            raise forms.ValidationError("Een applicatie met deze client_id bestaat al.")
        return client_id


class ApplicationEditForm(forms.ModelForm):
    redirect_uri = forms.URLField(label="Redirect URI", assume_scheme="https")
    requested_fields = forms.MultipleChoiceField(
        label="Gevraagde velden",
        choices=FIELD_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = Application
        fields = ["naam", "beschrijving", "requested_fields", "is_approved"]
        labels = {
            "naam": "Naam",
            "beschrijving": "Beschrijving",
            "is_approved": "Goedgekeurd",
        }
        widgets = {
            "beschrijving": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.oauth_app_id:
            self.fields["redirect_uri"].initial = self.instance.oauth_app.redirect_uris
        if self.instance and self.instance.pk:
            self.fields["requested_fields"].initial = self.instance.requested_fields

    def save(self, commit=True):
        # Oude requested_fields uit DB lezen vóór super().save: ModelForm overschrijft
        # de instance al met cleaned_data tijdens _post_clean.
        from .models import Application as _App

        previous_fields = set()
        if self.instance.pk:
            previous_fields = set(
                _App.objects.filter(pk=self.instance.pk).values_list("requested_fields", flat=True).first() or []
            )
        app = super().save(commit=False)
        new_fields = self.cleaned_data["requested_fields"]
        # Snoei bestaande consents: een veld dat uit requested_fields verdwijnt mag
        # niet stilletjes terugkomen als de admin het later opnieuw toevoegt — de
        # gebruiker moet dan expliciet opnieuw toestemming geven.
        removed = previous_fields - set(new_fields)
        app.requested_fields = new_fields
        if commit:
            app.save()
            if removed:
                from .models import Consent

                for consent in Consent.objects.filter(application=app, revoked_at__isnull=True):
                    pruned = [f for f in consent.granted_fields if f not in removed]
                    if pruned != consent.granted_fields:
                        consent.granted_fields = pruned
                        consent.save(update_fields=["granted_fields"])
            if app.oauth_app_id:
                app.oauth_app.redirect_uris = self.cleaned_data["redirect_uri"]
                app.oauth_app.name = app.naam
                app.oauth_app.save(update_fields=["redirect_uris", "name"])
        return app
