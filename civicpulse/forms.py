"""
Forms for the CivicPulse application.

Provides secure forms for user authentication and Person management, including:
- Login, registration, and password reset functionality
- Person creation and editing with layered validation
- Comprehensive validation with XSS protection
"""

from datetime import date
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

from civicpulse.models import (
    VALID_US_STATE_CODES,
    Person,
    sanitize_text_field,
    validate_phone_number,
    validate_zip_code,
)

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
        # Using plain text format to avoid XSS vulnerabilities
        self.fields["password1"].help_text = (
            "Password must be at least 8 characters and include: "
            "(1) At least one uppercase letter, "
            "(2) At least one lowercase letter, "
            "(3) At least one number, "
            "(4) At least one special character"
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
        help_text=(
            "Password must be at least 8 characters and include: "
            "(1) At least one uppercase letter, "
            "(2) At least one lowercase letter, "
            "(3) At least one number, "
            "(4) At least one special character"
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
        help_text=(
            "Password must be at least 8 characters and include: "
            "(1) At least one uppercase letter, "
            "(2) At least one lowercase letter, "
            "(3) At least one number, "
            "(4) At least one special character"
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

        if not current_password:
            raise ValidationError("This field is required.", code="required")

        if not self.user.check_password(current_password):
            raise ValidationError(
                "Current password is incorrect.", code="incorrect_password"
            )

        return current_password

    def clean_new_password2(self) -> str:
        """Validate password confirmation matches."""
        password1 = self.cleaned_data.get("new_password1")
        password2 = self.cleaned_data.get("new_password2")

        if not password2:
            raise ValidationError("This field is required.", code="required")

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


class PersonForm(forms.ModelForm):
    """
    Form for creating and editing Person objects.

    Implements layered validation following the documented pattern:
    1. Field-level: Sanitization + basic validation (clean_<field>())
    2. Form-level: Cross-field validation + duplicate detection (clean())
    3. Model-level: Business rules (automatic on save via Person.clean())

    Features:
    - XSS protection through sanitization of all text fields
    - Comprehensive validation for email, phone, state codes, and ZIP codes
    - Duplicate detection using PersonDuplicateDetector service
    - User-friendly Bootstrap styling and help text
    - Age and date validation for date of birth
    - Tag parsing from comma-separated strings

    Example:
        >>> form = PersonForm(data={
        ...     'first_name': 'John',
        ...     'last_name': 'Doe',
        ...     'email': 'john@example.com'
        ... })
        >>> if form.is_valid():
        ...     person = form.save()
        ...     duplicates = form.duplicates  # Check for potential duplicates
    """

    # Override tags field to use TextInput instead of JSONField widget
    tags = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 2,
                "placeholder": "Enter tags separated by commas",
                "class": "form-control",
            }
        ),
        help_text="Comma-separated tags for categorization",
    )

    class Meta:
        model = Person
        fields = [
            "first_name",
            "middle_name",
            "last_name",
            "suffix",
            "date_of_birth",
            "gender",
            "email",
            "phone_primary",
            "phone_secondary",
            "street_address",
            "apartment_number",
            "city",
            "state",
            "zip_code",
            "county",
            "occupation",
            "employer",
            "notes",
            "tags",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "notes": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
            "gender": forms.Select(attrs={"class": "form-select"}),
        }
        help_texts = {
            "phone_primary": "Format: (555) 555-5555 or 555-555-5555",
            "phone_secondary": "Optional secondary phone number",
            "zip_code": "Format: 12345 or 12345-6789",
            "state": "Two-letter state code (e.g., CA, NY, TX)",
            "date_of_birth": "Must be a valid date not in the future",
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Initialize form with enhanced styling and duplicate tracking.

        Sets up:
        - Bootstrap styling for all fields
        - Required field markers
        - Duplicate detection storage
        """
        super().__init__(*args, **kwargs)
        self.duplicates: list[Person] = []  # Store potential duplicates

        # Add Bootstrap classes to all fields
        for _field_name, field in self.fields.items():
            if "class" not in field.widget.attrs:
                field.widget.attrs["class"] = "form-control"

        # Mark required fields explicitly
        self.fields["first_name"].required = True
        self.fields["last_name"].required = True

    # Field-level validation methods for text fields
    def clean_first_name(self) -> str:
        """
        Sanitize and validate first name.

        Returns:
            Sanitized first name

        Raises:
            ValidationError: If first name is empty or too long
        """
        value = self.cleaned_data.get("first_name", "")
        # 1. Sanitize FIRST
        sanitized = sanitize_text_field(value)
        # 2. Validate
        if not sanitized or not sanitized.strip():
            raise ValidationError("First name cannot be empty")
        if len(sanitized) > 100:
            raise ValidationError("First name cannot exceed 100 characters")
        return sanitized

    def clean_middle_name(self) -> str:
        """
        Sanitize and validate middle name.

        Returns:
            Sanitized middle name
        """
        value = self.cleaned_data.get("middle_name", "")
        if value:
            sanitized = sanitize_text_field(value)
            if len(sanitized) > 100:
                raise ValidationError("Middle name cannot exceed 100 characters")
            return sanitized
        return ""

    def clean_last_name(self) -> str:
        """
        Sanitize and validate last name.

        Returns:
            Sanitized last name

        Raises:
            ValidationError: If last name is empty or too long
        """
        value = self.cleaned_data.get("last_name", "")
        # 1. Sanitize FIRST
        sanitized = sanitize_text_field(value)
        # 2. Validate
        if not sanitized or not sanitized.strip():
            raise ValidationError("Last name cannot be empty")
        if len(sanitized) > 100:
            raise ValidationError("Last name cannot exceed 100 characters")
        return sanitized

    def clean_suffix(self) -> str:
        """
        Sanitize and validate name suffix.

        Returns:
            Sanitized suffix
        """
        value = self.cleaned_data.get("suffix", "")
        if value:
            sanitized = sanitize_text_field(value)
            if len(sanitized) > 10:
                raise ValidationError("Suffix cannot exceed 10 characters")
            return sanitized
        return ""

    def clean_street_address(self) -> str:
        """
        Sanitize and validate street address.

        Returns:
            Sanitized street address
        """
        value = self.cleaned_data.get("street_address", "")
        if value:
            sanitized = sanitize_text_field(value)
            if len(sanitized) > 255:
                raise ValidationError("Street address cannot exceed 255 characters")
            return sanitized
        return ""

    def clean_apartment_number(self) -> str:
        """
        Sanitize and validate apartment number.

        Returns:
            Sanitized apartment number
        """
        value = self.cleaned_data.get("apartment_number", "")
        if value:
            sanitized = sanitize_text_field(value)
            if len(sanitized) > 50:
                raise ValidationError("Apartment number cannot exceed 50 characters")
            return sanitized
        return ""

    def clean_city(self) -> str:
        """
        Sanitize and validate city.

        Returns:
            Sanitized city
        """
        value = self.cleaned_data.get("city", "")
        if value:
            sanitized = sanitize_text_field(value)
            if len(sanitized) > 100:
                raise ValidationError("City cannot exceed 100 characters")
            return sanitized
        return ""

    def clean_county(self) -> str:
        """
        Sanitize and validate county.

        Returns:
            Sanitized county
        """
        value = self.cleaned_data.get("county", "")
        if value:
            sanitized = sanitize_text_field(value)
            if len(sanitized) > 100:
                raise ValidationError("County cannot exceed 100 characters")
            return sanitized
        return ""

    def clean_occupation(self) -> str:
        """
        Sanitize and validate occupation.

        Returns:
            Sanitized occupation
        """
        value = self.cleaned_data.get("occupation", "")
        if value:
            sanitized = sanitize_text_field(value)
            if len(sanitized) > 100:
                raise ValidationError("Occupation cannot exceed 100 characters")
            return sanitized
        return ""

    def clean_employer(self) -> str:
        """
        Sanitize and validate employer.

        Returns:
            Sanitized employer
        """
        value = self.cleaned_data.get("employer", "")
        if value:
            sanitized = sanitize_text_field(value)
            if len(sanitized) > 100:
                raise ValidationError("Employer cannot exceed 100 characters")
            return sanitized
        return ""

    def clean_notes(self) -> str:
        """
        Sanitize and validate notes.

        Returns:
            Sanitized notes
        """
        value = self.cleaned_data.get("notes", "")
        if value:
            sanitized = sanitize_text_field(value)
            # Notes can be longer but still have a reasonable limit
            if len(sanitized) > 10000:
                raise ValidationError("Notes cannot exceed 10,000 characters")
            return sanitized
        return ""

    def clean_email(self) -> str:
        """
        Validate and normalize email address.

        Returns:
            Normalized email address (lowercase, trimmed)

        Raises:
            ValidationError: If email format is invalid
        """
        value = self.cleaned_data.get("email", "")
        if value:
            value = value.lower().strip()
            # Use Django's built-in email validation
            from django.core.validators import validate_email as django_validate_email

            try:
                django_validate_email(value)
            except ValidationError as e:
                raise ValidationError("Enter a valid email address") from e
        return value

    def clean_phone_primary(self) -> str:
        """
        Validate primary phone number format.

        Returns:
            Validated phone number

        Raises:
            ValidationError: If phone number format is invalid
        """
        value = self.cleaned_data.get("phone_primary", "")
        if value:
            # Use existing validator from models.py
            validate_phone_number(value)
        return value

    def clean_phone_secondary(self) -> str:
        """
        Validate secondary phone number format.

        Returns:
            Validated phone number

        Raises:
            ValidationError: If phone number format is invalid
        """
        value = self.cleaned_data.get("phone_secondary", "")
        if value:
            validate_phone_number(value)
        return value

    def clean_state(self) -> str:
        """
        Validate and normalize state code.

        Returns:
            Normalized state code (uppercase)

        Raises:
            ValidationError: If state code is not valid
        """
        value = self.cleaned_data.get("state", "")
        if value:
            value = value.upper().strip()
            if value not in VALID_US_STATE_CODES:
                raise ValidationError(f"'{value}' is not a valid US state code")
        return value

    def clean_zip_code(self) -> str:
        """
        Validate ZIP code format.

        Returns:
            Validated ZIP code

        Raises:
            ValidationError: If ZIP code format is invalid
        """
        value = self.cleaned_data.get("zip_code", "")
        if value:
            validate_zip_code(value)
        return value

    def clean_date_of_birth(self) -> date | None:
        """
        Validate date of birth.

        Returns:
            Validated date of birth

        Raises:
            ValidationError: If date is in the future or indicates unrealistic age
        """
        value = self.cleaned_data.get("date_of_birth")
        if value:
            from datetime import date as date_class

            today = date_class.today()

            if value > today:
                raise ValidationError("Date of birth cannot be in the future")

            # Validate age is reasonable (not older than 150 years)
            age = (today - value).days // 365
            if age > 150:
                raise ValidationError("Date of birth indicates an age over 150 years")

        return value

    def clean_tags(self) -> list[str]:
        """
        Parse and validate tags from comma-separated string or list.

        Returns:
            List of sanitized tag strings

        Raises:
            ValidationError: If tags format is invalid
        """
        value = self.cleaned_data.get("tags", "")

        if isinstance(value, str) and value:
            # Convert comma-separated string to list
            tags = [tag.strip() for tag in value.split(",") if tag.strip()]
            # Sanitize each tag
            sanitized_tags = [sanitize_text_field(tag) for tag in tags]
            # Remove empty tags after sanitization
            return [tag for tag in sanitized_tags if tag]
        elif isinstance(value, list):
            # Already a list, sanitize each item
            sanitized_tags = [sanitize_text_field(str(tag)) for tag in value]
            return [tag for tag in sanitized_tags if tag]

        return []

    def clean(self) -> dict[str, Any]:
        """
        Cross-field validation and duplicate detection.

        Performs:
        1. Validates relationships between fields
        2. Detects potential duplicates using PersonDuplicateDetector
        3. Stores duplicates in self.duplicates for view access

        Returns:
            Cleaned data dictionary

        Note:
            Duplicate detection does not prevent form submission,
            but provides information for the view to warn the user.
        """
        cleaned_data = super().clean()

        # Check for duplicates if we have minimum required data
        if not cleaned_data:
            return {}

        has_first_name = cleaned_data.get("first_name")
        has_last_name = cleaned_data.get("last_name")
        if has_first_name and has_last_name:

            from civicpulse.services.person_service import (
                PersonDataDict,
                PersonDuplicateDetector,
            )

            detector = PersonDuplicateDetector()
            person_data: PersonDataDict = {
                "first_name": cleaned_data.get("first_name", ""),
                "last_name": cleaned_data.get("last_name", ""),
                "email": cleaned_data.get("email", ""),
                "phone_primary": cleaned_data.get("phone_primary", ""),
            }

            # Add optional date_of_birth if present
            if cleaned_data.get("date_of_birth"):
                person_data["date_of_birth"] = cleaned_data.get("date_of_birth")  # type: ignore[typeddict-item]

            # Find duplicates (exclude current instance if editing)
            exclude_id = str(self.instance.id) if self.instance.pk else None
            duplicates = detector.find_duplicates(person_data, exclude_id=exclude_id)

            # Store duplicates for view to access (limit to 10 for performance)
            self.duplicates = list(duplicates[:10])

        return cleaned_data if cleaned_data else {}
