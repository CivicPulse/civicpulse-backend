from django import forms

from .models import (
    Candidate,
    ContactAttempt,
    ContactEffort,
    Election,
    ElectionDate,
    Office,
)


class CampaignForm(forms.ModelForm):
    """Form for creating and editing contact campaigns."""

    class Meta:
        model = ContactEffort
        fields = ["name", "description", "script", "is_active", "election", "candidate"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-green-500 focus:border-green-500 block w-full p-2.5",
                    "placeholder": "Campaign name",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-green-500 focus:border-green-500 block w-full p-2.5",
                    "rows": 3,
                    "placeholder": "Brief description of this campaign...",
                }
            ),
            "script": forms.Textarea(
                attrs={
                    "class": "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-green-500 focus:border-green-500 block w-full p-2.5",
                    "rows": 8,
                    "placeholder": "Script or talking points for callers...",
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "w-4 h-4 text-green-600 bg-gray-100 border-gray-300 rounded focus:ring-green-500",
                }
            ),
            "election": forms.Select(
                attrs={
                    "class": "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-green-500 focus:border-green-500 block w-full p-2.5",
                }
            ),
            "candidate": forms.Select(
                attrs={
                    "class": "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-green-500 focus:border-green-500 block w-full p-2.5",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["election"].required = False
        self.fields["candidate"].required = False
        self.fields["election"].queryset = Election.objects.select_related(
            "office"
        ).order_by("-year", "-election_day")
        # Filter candidates based on selected election
        if self.instance and self.instance.election_id:
            self.fields["candidate"].queryset = Candidate.objects.filter(
                election=self.instance.election
            ).select_related("person")
        elif self.data.get("election"):
            try:
                election_id = self.data.get("election")
                self.fields["candidate"].queryset = Candidate.objects.filter(
                    election_id=election_id
                ).select_related("person")
            except (ValueError, TypeError):
                self.fields["candidate"].queryset = Candidate.objects.none()
        else:
            self.fields["candidate"].queryset = Candidate.objects.none()


class ContactAttemptForm(forms.ModelForm):
    """Form for logging contact attempt outcomes."""

    class Meta:
        model = ContactAttempt
        fields = [
            "outcome",
            "contact_type",
            "notes",
            "phone_number_used",
            "callback_time",
        ]
        widgets = {
            "outcome": forms.RadioSelect(
                attrs={
                    "class": "hidden peer",
                }
            ),
            "contact_type": forms.RadioSelect(
                attrs={
                    "class": "hidden peer",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-green-500 focus:border-green-500 block w-full p-2.5",
                    "rows": 3,
                    "placeholder": "Conversation notes (optional)...",
                }
            ),
            "phone_number_used": forms.HiddenInput(),
            "callback_time": forms.DateTimeInput(
                attrs={
                    "class": "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-green-500 focus:border-green-500 block w-full p-2.5",
                    "type": "datetime-local",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["callback_time"].required = False
        self.fields["notes"].required = False
        self.fields["phone_number_used"].required = False


class AssignmentFilterForm(forms.Form):
    """Filter form for bulk assigning persons to a campaign."""

    party = forms.ChoiceField(
        required=False,
        choices=[
            ("", "Any Party"),
            ("Democratic", "Democratic"),
            ("Republican", "Republican"),
            ("Independent", "Independent"),
            ("Libertarian", "Libertarian"),
            ("Green", "Green"),
            ("No Party", "No Party"),
        ],
        widget=forms.Select(
            attrs={
                "class": "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-green-500 focus:border-green-500 block w-full p-2.5",
            }
        ),
    )
    likelihood = forms.ChoiceField(
        required=False,
        choices=[
            ("", "Any Likelihood"),
            ("high", "High (70%+)"),
            ("medium", "Medium (40-69%)"),
            ("low", "Low (<40%)"),
        ],
        widget=forms.Select(
            attrs={
                "class": "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-green-500 focus:border-green-500 block w-full p-2.5",
            }
        ),
    )
    has_phone = forms.BooleanField(
        required=False,
        initial=True,
        label="Has phone number",
        widget=forms.CheckboxInput(
            attrs={
                "class": "w-4 h-4 text-green-600 bg-gray-100 border-gray-300 rounded focus:ring-green-500",
            }
        ),
    )
    limit = forms.IntegerField(
        required=False,
        initial=100,
        min_value=1,
        max_value=10000,
        label="Max to assign",
        widget=forms.NumberInput(
            attrs={
                "class": "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-green-500 focus:border-green-500 block w-full p-2.5",
            }
        ),
    )


# Election-related forms

TAILWIND_INPUT = "bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-green-500 focus:border-green-500 block w-full p-2.5"
TAILWIND_SELECT = TAILWIND_INPUT
TAILWIND_CHECKBOX = (
    "w-4 h-4 text-green-600 bg-gray-100 border-gray-300 rounded focus:ring-green-500"
)


class OfficeForm(forms.ModelForm):
    """Form for creating and editing elected offices."""

    class Meta:
        model = Office
        fields = [
            "name",
            "level",
            "city",
            "county",
            "state",
            "term_length_years",
            "description",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": TAILWIND_INPUT,
                    "placeholder": "e.g., Mayor, City Council Seat 3",
                }
            ),
            "level": forms.Select(attrs={"class": TAILWIND_SELECT}),
            "city": forms.TextInput(
                attrs={
                    "class": TAILWIND_INPUT,
                    "placeholder": "City name",
                }
            ),
            "county": forms.TextInput(
                attrs={
                    "class": TAILWIND_INPUT,
                    "placeholder": "County name",
                }
            ),
            "state": forms.TextInput(
                attrs={
                    "class": TAILWIND_INPUT,
                    "placeholder": "GA",
                    "maxlength": "2",
                }
            ),
            "term_length_years": forms.NumberInput(
                attrs={
                    "class": TAILWIND_INPUT,
                    "placeholder": "4",
                    "min": "1",
                    "max": "10",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": TAILWIND_INPUT,
                    "rows": 3,
                    "placeholder": "Description of this office...",
                }
            ),
        }


class ElectionForm(forms.ModelForm):
    """Form for creating and editing elections."""

    class Meta:
        model = Election
        fields = [
            "office",
            "election_type",
            "year",
            "status",
            "description",
            "parent_election",
            "qualifying_start",
            "qualifying_end",
            "registration_deadline",
            "absentee_request_deadline",
            "early_voting_start",
            "early_voting_end",
            "election_day",
            "certification_date",
        ]
        widgets = {
            "office": forms.Select(attrs={"class": TAILWIND_SELECT}),
            "election_type": forms.Select(attrs={"class": TAILWIND_SELECT}),
            "year": forms.NumberInput(
                attrs={
                    "class": TAILWIND_INPUT,
                    "placeholder": "2025",
                    "min": "2000",
                    "max": "2100",
                }
            ),
            "status": forms.Select(attrs={"class": TAILWIND_SELECT}),
            "parent_election": forms.Select(attrs={"class": TAILWIND_SELECT}),
            "description": forms.Textarea(
                attrs={
                    "class": TAILWIND_INPUT,
                    "rows": 3,
                    "placeholder": "Additional notes about this election...",
                }
            ),
            "qualifying_start": forms.DateInput(
                attrs={"class": TAILWIND_INPUT, "type": "date"}
            ),
            "qualifying_end": forms.DateInput(
                attrs={"class": TAILWIND_INPUT, "type": "date"}
            ),
            "registration_deadline": forms.DateInput(
                attrs={"class": TAILWIND_INPUT, "type": "date"}
            ),
            "absentee_request_deadline": forms.DateInput(
                attrs={"class": TAILWIND_INPUT, "type": "date"}
            ),
            "early_voting_start": forms.DateInput(
                attrs={"class": TAILWIND_INPUT, "type": "date"}
            ),
            "early_voting_end": forms.DateInput(
                attrs={"class": TAILWIND_INPUT, "type": "date"}
            ),
            "election_day": forms.DateInput(
                attrs={"class": TAILWIND_INPUT, "type": "date"}
            ),
            "certification_date": forms.DateInput(
                attrs={"class": TAILWIND_INPUT, "type": "date"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make parent_election only show elections that could be parents
        self.fields["parent_election"].required = False
        self.fields["parent_election"].queryset = Election.objects.filter(
            election_type=Election.ElectionType.GENERAL
        ).order_by("-year")


class CandidateForm(forms.ModelForm):
    """Form for creating and editing candidates."""

    class Meta:
        model = Candidate
        fields = [
            "name",
            "person",
            "party_affiliation",
            "is_incumbent",
            "status",
            "campaign_website",
            "campaign_slogan",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": TAILWIND_INPUT,
                    "placeholder": "Candidate name",
                }
            ),
            "person": forms.Select(attrs={"class": TAILWIND_SELECT}),
            "party_affiliation": forms.TextInput(
                attrs={
                    "class": TAILWIND_INPUT,
                    "placeholder": "e.g., Democratic, Republican",
                }
            ),
            "is_incumbent": forms.CheckboxInput(attrs={"class": TAILWIND_CHECKBOX}),
            "status": forms.Select(attrs={"class": TAILWIND_SELECT}),
            "campaign_website": forms.URLInput(
                attrs={
                    "class": TAILWIND_INPUT,
                    "placeholder": "https://example.com",
                }
            ),
            "campaign_slogan": forms.TextInput(
                attrs={
                    "class": TAILWIND_INPUT,
                    "placeholder": "Campaign slogan...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].required = False
        self.fields["person"].required = False

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get("name")
        person = cleaned_data.get("person")

        # Require at least one of name or person
        if not name and not person:
            raise forms.ValidationError(
                "Please provide either a name or select a person record."
            )
        return cleaned_data


class ElectionDateForm(forms.ModelForm):
    """Form for adding additional election dates."""

    class Meta:
        model = ElectionDate
        fields = ["date_type", "date", "description", "location"]
        widgets = {
            "date_type": forms.Select(attrs={"class": TAILWIND_SELECT}),
            "date": forms.DateInput(attrs={"class": TAILWIND_INPUT, "type": "date"}),
            "description": forms.TextInput(
                attrs={
                    "class": TAILWIND_INPUT,
                    "placeholder": "Description of this date...",
                }
            ),
            "location": forms.TextInput(
                attrs={
                    "class": TAILWIND_INPUT,
                    "placeholder": "Location (optional)",
                }
            ),
        }
