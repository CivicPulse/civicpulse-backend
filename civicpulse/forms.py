from django import forms

from .models import ContactAttempt, ContactEffort


class CampaignForm(forms.ModelForm):
    """Form for creating and editing contact campaigns."""

    class Meta:
        model = ContactEffort
        fields = ["name", "description", "script", "is_active"]
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
        }


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
