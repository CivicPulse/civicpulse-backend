# Generated manually for CheckingAccount and Transaction models

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("civicpulse", "0016_effortassignment_assignment_must_have_target"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CheckingAccount",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "account_number_last4",
                    models.CharField(
                        help_text="Last 4 digits of account number only",
                        max_length=4,
                    ),
                ),
                (
                    "institution_name",
                    models.CharField(
                        help_text="Bank or financial institution name",
                        max_length=200,
                    ),
                ),
                (
                    "account_nickname",
                    models.CharField(
                        blank=True,
                        help_text="Optional nickname for easy identification",
                        max_length=100,
                    ),
                ),
                (
                    "opened_date",
                    models.DateField(
                        help_text="Date the account was opened",
                    ),
                ),
                (
                    "closed_date",
                    models.DateField(
                        blank=True,
                        help_text="Date the account was closed (if applicable)",
                        null=True,
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(default=True),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True),
                ),
                (
                    "campaign",
                    models.ForeignKey(
                        help_text="The campaign this account belongs to",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="checking_accounts",
                        to="civicpulse.campaign",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="checking_accounts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "checking account",
                "verbose_name_plural": "checking accounts",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="Transaction",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "posted_date",
                    models.DateField(
                        help_text="Date transaction was posted to account",
                    ),
                ),
                (
                    "transaction_date",
                    models.DateField(
                        help_text="Date of the transaction",
                    ),
                ),
                (
                    "transaction_type",
                    models.CharField(
                        choices=[
                            ("deposit", "Deposit"),
                            ("debit", "Debit"),
                            ("credit", "Credit"),
                            ("check", "Check"),
                            ("transfer", "Transfer"),
                            ("fee", "Fee"),
                            ("other", "Other"),
                        ],
                        default="other",
                        max_length=20,
                    ),
                ),
                (
                    "check_number",
                    models.CharField(
                        blank=True,
                        help_text="Check or serial number (if applicable)",
                        max_length=20,
                    ),
                ),
                (
                    "description",
                    models.CharField(
                        help_text="Transaction description from bank statement",
                        max_length=500,
                    ),
                ),
                (
                    "amount_cents",
                    models.IntegerField(
                        help_text="Amount in cents, negative for debits/withdrawals",
                    ),
                ),
                (
                    "import_batch",
                    models.CharField(
                        blank=True,
                        help_text="UUID of the import batch for tracking",
                        max_length=36,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "account",
                    models.ForeignKey(
                        help_text="The checking account this transaction belongs to",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="transactions",
                        to="civicpulse.checkingaccount",
                    ),
                ),
            ],
            options={
                "verbose_name": "transaction",
                "verbose_name_plural": "transactions",
                "ordering": ["-posted_date", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="transaction",
            index=models.Index(
                fields=["account", "posted_date"],
                name="civicpulse__account_posted_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="transaction",
            index=models.Index(
                fields=["import_batch"],
                name="civicpulse__import_batch_idx",
            ),
        ),
    ]
