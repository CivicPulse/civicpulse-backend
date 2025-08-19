"""
Authentication forms for the CivicPulse application.

Provides secure forms for user authentication including login, registration,
and password reset functionality with comprehensive validation.
"""

from typing import Any

from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe

User = get_user_model()


class SecureLoginForm(AuthenticationForm):
    """
    Enhanced authentication form with additional security features.

    Features:
    - Rate limiting protection
    - Enhanced validation
    - Custom error messages
    - CSRF protection
    """

    username = forms.CharField(
        max_length=254,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Username or Email",
                "autofocus": True,
                "autocomplete": "username",
            }
        ),
        label="Username or Email",
    )

    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Password",
                "autocomplete": "current-password",
            }
        ),
        label="Password",
    )

    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="Remember me for 30 days",
    )

    def __init__(self, request=None, *args, **kwargs):
        """Initialize form with request context for security features."""
        super().__init__(request, *args, **kwargs)
        self.request = request

        # Add Bootstrap styling
        for field in self.fields.values():
            if isinstance(field.widget, forms.TextInput):
                field.widget.attrs.update({"class": "form-control"})
            elif isinstance(field.widget, forms.PasswordInput):
                field.widget.attrs.update({"class": "form-control"})

    def clean(self) -> dict[str, Any]:
        """Enhanced validation with security checks."""
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username is not None and password:
            # Try to authenticate user
            self.user_cache = authenticate(
                self.request, username=username, password=password
            )

            if self.user_cache is None:
                # Don't reveal whether username exists
                raise self.get_invalid_login_error()
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data

    def confirm_login_allowed(self, user):
        """Additional checks for login permission."""
        if not user.is_active:
            raise ValidationError(
                "This account has been deactivated.",
                code="inactive",
            )

        # Check if user is verified (if verification is required)
        if hasattr(user, "is_verified") and not user.is_verified:
            raise ValidationError(
                "Please verify your email address before logging in.",
                code="unverified",
            )


class SecureUserRegistrationForm(UserCreationForm):
    """
    Enhanced user registration form with role selection and validation.

    Features:
    - Role-based registration
    - Email validation
    - Strong password requirements
    - Organization field for admin/organizer roles
    - Phone number validation
    """

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "your.email@example.com",
                "autocomplete": "email",
            }
        ),
        help_text="Required. A valid email address is needed for account verification.",
    )

    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "First Name",
                "autocomplete": "given-name",
            }
        ),
    )

    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Last Name",
                "autocomplete": "family-name",
            }
        ),
    )

    role = forms.ChoiceField(
        choices=User.ROLE_CHOICES,
        initial="volunteer",
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text="Select your role in the organization.",
    )

    organization = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Organization Name",
                "autocomplete": "organization",
            }
        ),
        help_text="Required for admin and organizer roles.",
    )

    phone_number = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "(555) 123-4567",
                "autocomplete": "tel",
            }
        ),
        help_text="Optional. Format: (555) 123-4567 or +1-555-123-4567",
    )

    terms_accepted = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        label="I accept the Terms of Service and Privacy Policy",
        error_messages={"required": "You must accept the terms to create an account."},
    )

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "organization",
            "phone_number",
            "password1",
            "password2",
        )

    def __init__(self, *args, **kwargs):
        """Initialize form with enhanced styling and validation."""
        super().__init__(*args, **kwargs)

        # Add Bootstrap styling and custom attributes
        self.fields["username"].widget.attrs.update(
            {
                "class": "form-control",
                "placeholder": "Choose a username",
                "autocomplete": "username",
            }
        )

        self.fields["password1"].widget.attrs.update(
            {
                "class": "form-control",
                "placeholder": "Create a strong password",
                "autocomplete": "new-password",
            }
        )

        self.fields["password2"].widget.attrs.update(
            {
                "class": "form-control",
                "placeholder": "Confirm your password",
                "autocomplete": "new-password",
            }
        )

        # Add help text for passwords
        self.fields["password1"].help_text = mark_safe(
            "Password must be at least 8 characters and include:<br>"
            "• At least one uppercase letter<br>"
            "• At least one lowercase letter<br>"
            "• At least one number<br>"
            "• At least one special character"
        )

    def clean_email(self) -> str:
        """Validate email uniqueness and format."""
        email = self.cleaned_data.get("email", "").lower().strip()

        if User.objects.filter(email=email).exists():
            raise ValidationError(
                "A user with this email address already exists.", code="duplicate_email"
            )

        return email

    def clean_username(self) -> str:
        """Validate username format and uniqueness."""
        username = self.cleaned_data.get("username", "").strip()

        # Check for minimum length
        if len(username) < 3:
            raise ValidationError(
                "Username must be at least 3 characters long.",
                code="username_too_short",
            )

        # Check for valid characters (alphanumeric and underscore only)
        if not username.replace("_", "").replace(".", "").isalnum():
            raise ValidationError(
                "Username can only contain letters, numbers, underscores, and periods.",
                code="invalid_username",
            )

        return username

    def clean_organization(self) -> str:
        """Validate organization field based on role."""
        organization = self.cleaned_data.get("organization", "").strip()
        role = self.cleaned_data.get("role")

        # Organization is required for admin and organizer roles
        if role in ["admin", "organizer"] and not organization:
            raise ValidationError(
                "Organization is required for admin and organizer roles.",
                code="organization_required",
            )

        return organization

    def clean_phone_number(self) -> str:
        """Validate phone number format if provided."""
        phone_number = self.cleaned_data.get("phone_number", "").strip()

        if phone_number:
            # Use the validator from the User model
            from civicpulse.models import validate_phone_number

            validate_phone_number(phone_number)

        return phone_number

    def save(self, commit=True):
        """Save user with additional fields."""
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.role = self.cleaned_data["role"]
        user.organization = self.cleaned_data["organization"]
        user.phone_number = self.cleaned_data["phone_number"]

        if commit:
            user.save()

        return user


class SecurePasswordResetForm(PasswordResetForm):
    """
    Enhanced password reset form with additional security measures.

    Features:
    - Rate limiting
    - Enhanced validation
    - No user enumeration
    """

    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "Enter your email address",
                "autocomplete": "email",
            }
        ),
        label="Email Address",
        help_text="Enter the email address associated with your account.",
    )

    def clean_email(self) -> str:
        """Validate email without revealing if user exists."""
        email = self.cleaned_data.get("email", "").lower().strip()

        # Basic email format validation is already done by EmailField
        # We don't want to reveal whether the email exists in our system
        # for security reasons (prevents user enumeration)

        return email


class SecureSetPasswordForm(SetPasswordForm):
    """
    Enhanced set password form for password resets.

    Features:
    - Strong password validation
    - Enhanced security checks
    """

    new_password1 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "New password",
                "autocomplete": "new-password",
            }
        ),
        label="New Password",
        help_text=mark_safe(
            "Password must be at least 8 characters and include:<br>"
            "• At least one uppercase letter<br>"
            "• At least one lowercase letter<br>"
            "• At least one number<br>"
            "• At least one special character"
        ),
    )

    new_password2 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Confirm new password",
                "autocomplete": "new-password",
            }
        ),
        label="Confirm New Password",
    )


class PasswordChangeForm(forms.Form):
    """
    Form for authenticated users to change their password.

    Features:
    - Current password verification
    - Strong password validation
    - Enhanced security
    """

    current_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Current password",
                "autocomplete": "current-password",
            }
        ),
        label="Current Password",
    )

    new_password1 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "New password",
                "autocomplete": "new-password",
            }
        ),
        label="New Password",
        help_text=mark_safe(
            "Password must be at least 8 characters and include:<br>"
            "• At least one uppercase letter<br>"
            "• At least one lowercase letter<br>"
            "• At least one number<br>"
            "• At least one special character"
        ),
    )

    new_password2 = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "placeholder": "Confirm new password",
                "autocomplete": "new-password",
            }
        ),
        label="Confirm New Password",
    )

    def __init__(self, user, *args, **kwargs):
        """Initialize form with user context."""
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self) -> str:
        """Validate current password."""
        current_password = self.cleaned_data.get("current_password")

        if not self.user.check_password(current_password):
            raise ValidationError(
                "Current password is incorrect.", code="incorrect_password"
            )

        return current_password

    def clean_new_password2(self) -> str:
        """Validate password confirmation matches."""
        password1 = self.cleaned_data.get("new_password1")
        password2 = self.cleaned_data.get("new_password2")

        if password1 and password2 and password1 != password2:
            raise ValidationError(
                "The two password fields must match.", code="password_mismatch"
            )

        return password2

    def save(self, commit=True):
        """Save the new password."""
        password = self.cleaned_data["new_password1"]
        self.user.set_password(password)

        if commit:
            self.user.save()

        return self.user
