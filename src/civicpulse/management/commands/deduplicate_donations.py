from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from civicpulse.models import Donation


class Command(BaseCommand):
    help = "Find and merge duplicate donation records that were synced from Stripe"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report duplicates without deleting them",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        self.stdout.write("Scanning for duplicate donations...")

        # Find donations with same connection, charged_at, and amount_cents
        # that appear more than once (potential duplicates)
        duplicates = (
            Donation.objects.values("connection_id", "charged_at", "amount_cents")
            .annotate(count=Count("id"))
            .filter(count__gt=1)
        )

        total_groups = len(duplicates)
        if total_groups == 0:
            self.stdout.write(self.style.SUCCESS("No duplicate donations found."))
            return

        self.stdout.write(f"Found {total_groups} duplicate groups to process...")

        deleted_count = 0
        kept_count = 0
        errors = []

        for i, dup_group in enumerate(duplicates, 1):
            try:
                connection_id = dup_group["connection_id"]
                charged_at = dup_group["charged_at"]
                amount_cents = dup_group["amount_cents"]

                # Get all donations in this duplicate group
                donations = Donation.objects.filter(
                    connection_id=connection_id,
                    charged_at=charged_at,
                    amount_cents=amount_cents,
                ).order_by("stripe_charge_id")

                if dry_run:
                    self._report_duplicates(donations, i, dup_group["count"])
                else:
                    with transaction.atomic():
                        count = self._merge_duplicates(donations)
                        deleted_count += count
                        kept_count += 1

                if i % 10 == 0:
                    self.stdout.write(f"Processed {i}/{total_groups} groups...")

            except Exception as e:
                errors.append(f"Group {i}: {e}")
                if len(errors) >= 10:
                    self.stdout.write(
                        self.style.WARNING("Too many errors, stopping...")
                    )
                    break

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Dry run complete: {total_groups} duplicate groups found"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Deduplication complete: {deleted_count} duplicates removed, "
                    f"{kept_count} donations kept"
                )
            )

        if errors:
            self.stdout.write(self.style.ERROR(f"\n{len(errors)} errors:"))
            for error in errors:
                self.stdout.write(self.style.ERROR(f"  {error}"))

    def _report_duplicates(self, donations, group_num, count):
        """Report a duplicate group without modifying data."""
        self.stdout.write(f"\nDuplicate group #{group_num} ({count} records):")
        for donation in donations:
            charge_id = donation.stripe_charge_id or "(none)"
            pi_id = donation.stripe_payment_intent_id or "(none)"
            is_charge = charge_id.startswith("ch_")
            marker = " [KEEP]" if is_charge else " [DELETE]"
            self.stdout.write(
                f"  - ${donation.amount_cents / 100:.2f} | "
                f"charge={charge_id} | pi={pi_id}{marker}"
            )

    def _merge_duplicates(self, donations):
        """
        Merge duplicate donations, keeping the one with a proper charge ID.

        Strategy:
        1. Prefer keeping donations where stripe_charge_id starts with "ch_"
        2. Delete donations where stripe_charge_id starts with "pi_"
           (these are duplicates from PaymentIntent sync)
        3. If multiple ch_ records exist (rare), keep the first one

        Returns the number of records deleted.
        """
        donations_list = list(donations)

        if len(donations_list) <= 1:
            return 0

        # Separate into charge-based and payment_intent-based
        charge_donations = [
            d for d in donations_list if d.stripe_charge_id.startswith("ch_")
        ]
        pi_donations = [
            d for d in donations_list if d.stripe_charge_id.startswith("pi_")
        ]

        # Decide which to keep
        if charge_donations:
            # Keep the first charge-based donation
            keeper = charge_donations[0]
            to_delete = charge_donations[1:] + pi_donations
        elif pi_donations:
            # No charge donations, keep first PI donation
            keeper = pi_donations[0]
            to_delete = pi_donations[1:]
        else:
            # Neither pattern matches (edge case), keep first
            keeper = donations_list[0]
            to_delete = donations_list[1:]

        # If we have a charge to keep and PI donations to delete,
        # copy the payment_intent_id to the keeper for audit trail
        if keeper.stripe_charge_id.startswith("ch_") and not keeper.stripe_payment_intent_id:
            for pi_donation in pi_donations:
                if pi_donation.stripe_charge_id.startswith("pi_"):
                    # The pi_ ID in stripe_charge_id is actually the payment intent ID
                    keeper.stripe_payment_intent_id = pi_donation.stripe_charge_id
                    keeper.save(update_fields=["stripe_payment_intent_id"])
                    break

        # Delete the duplicates
        delete_count = len(to_delete)
        if to_delete:
            delete_ids = [d.id for d in to_delete]
            Donation.objects.filter(id__in=delete_ids).delete()

        return delete_count
