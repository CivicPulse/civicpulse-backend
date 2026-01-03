"""
Stripe Connect integration service for CivicPulse.

Provides OAuth flow, token management, and charge syncing for connected Stripe accounts.
"""

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone

from stripe import StripeClient
from stripe.oauth_error import OAuthError

from civicpulse.conf import stripe_settings

logger = logging.getLogger(__name__)


class StripeConnectError(Exception):
    """Base exception for Stripe Connect errors."""

    pass


@dataclass
class OAuthResult:
    """Result of a Stripe OAuth token exchange."""

    access_token: str
    refresh_token: str
    stripe_user_id: str
    stripe_publishable_key: str
    livemode: bool
    scope: str


@dataclass
class ChargeData:
    """Stripe charge data for donation sync."""

    id: str
    amount_cents: int
    currency: str
    customer_id: str | None
    status: str
    description: str | None
    receipt_url: str | None
    created: datetime
    source_type: str = "charge"  # "charge" or "payment_intent"
    payment_intent_id: str | None = None  # For charges: the parent PaymentIntent ID
    latest_charge_id: str | None = None  # For payment_intents: the associated Charge ID


class StripeConnectService:
    """
    Service for Stripe Connect OAuth and API operations.

    Handles OAuth authorization, token exchange/refresh, deauthorization,
    and syncing charges from connected accounts.
    """

    def __init__(self):
        """Initialize the Stripe Connect service."""
        self._validate_config()
        self.client = StripeClient(
            api_key=stripe_settings.SECRET_KEY,
            client_id=stripe_settings.CLIENT_ID,
        )
        logger.info("Stripe Connect service initialized")

    def _validate_config(self):
        """Validate required Stripe configuration."""
        if not stripe_settings.is_configured:
            raise StripeConnectError(
                "Stripe not configured. Set CIVICPULSE_STRIPE['CLIENT_ID'] and "
                "CIVICPULSE_STRIPE['SECRET_KEY'] in Django settings."
            )

    def get_oauth_url(self, state: str, redirect_uri: str) -> str:
        """
        Generate Stripe Connect OAuth authorization URL.

        Args:
            state: CSRF protection token (should be random and stored in session)
            redirect_uri: URL to redirect to after authorization

        Returns:
            Full authorization URL to redirect the user to

        Example:
            url = service.get_oauth_url(
                state=request.session['oauth_state'],
                redirect_uri='https://example.com/stripe/callback'
            )
        """
        try:
            url = self.client.oauth.authorize_url(
                scope=stripe_settings.OAUTH_SCOPE,
                redirect_uri=redirect_uri,
                state=state,
            )
            logger.info(
                f"Generated OAuth URL with scope: {stripe_settings.OAUTH_SCOPE}"
            )
            return url
        except Exception as e:
            logger.error(f"Failed to generate OAuth URL: {e}")
            raise StripeConnectError(f"Failed to generate OAuth URL: {e}") from e

    def exchange_code(self, code: str) -> OAuthResult:
        """
        Exchange OAuth authorization code for access tokens.

        Args:
            code: Authorization code from OAuth callback

        Returns:
            OAuthResult with access token, refresh token, and account details

        Raises:
            StripeConnectError: If token exchange fails
        """
        try:
            response = self.client.oauth.token(
                params={"grant_type": "authorization_code", "code": code}
            )

            logger.info(
                f"Successfully exchanged code for account: {response['stripe_user_id']}"
            )

            return OAuthResult(
                access_token=response["access_token"],
                refresh_token=response["refresh_token"],
                stripe_user_id=response["stripe_user_id"],
                stripe_publishable_key=response["stripe_publishable_key"],
                livemode=response["livemode"],
                scope=response["scope"],
            )
        except OAuthError as e:
            logger.error(f"OAuth token exchange failed: {e}")
            raise StripeConnectError(f"OAuth token exchange failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during token exchange: {e}")
            raise StripeConnectError(
                f"Failed to exchange authorization code: {e}"
            ) from e

    def refresh_access_token(self, refresh_token: str) -> OAuthResult:
        """
        Refresh an expired access token using a refresh token.

        Args:
            refresh_token: Refresh token from initial authorization

        Returns:
            OAuthResult with new access token and account details

        Raises:
            StripeConnectError: If token refresh fails
        """
        try:
            response = self.client.oauth.token(
                params={"grant_type": "refresh_token", "refresh_token": refresh_token}
            )

            logger.info(
                f"Successfully refreshed token for account: {response['stripe_user_id']}"
            )

            return OAuthResult(
                access_token=response["access_token"],
                refresh_token=response.get("refresh_token", refresh_token),
                stripe_user_id=response["stripe_user_id"],
                stripe_publishable_key=response["stripe_publishable_key"],
                livemode=response["livemode"],
                scope=response["scope"],
            )
        except OAuthError as e:
            logger.error(f"Token refresh failed: {e}")
            raise StripeConnectError(f"Token refresh failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during token refresh: {e}")
            raise StripeConnectError(f"Failed to refresh access token: {e}") from e

    def deauthorize(self, stripe_user_id: str) -> bool:
        """
        Deauthorize a connected Stripe account.

        Args:
            stripe_user_id: Stripe account ID to deauthorize

        Returns:
            True if deauthorization succeeded

        Raises:
            StripeConnectError: If deauthorization fails
        """
        try:
            self.client.oauth.deauthorize(params={"stripe_user_id": stripe_user_id})
            logger.info(f"Successfully deauthorized account: {stripe_user_id}")
            return True
        except OAuthError as e:
            logger.error(f"Deauthorization failed for {stripe_user_id}: {e}")
            raise StripeConnectError(f"Deauthorization failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during deauthorization: {e}")
            raise StripeConnectError(f"Failed to deauthorize account: {e}") from e

    def list_charges(
        self,
        stripe_account_id: str,
        starting_after: str | None = None,
        limit: int = 100,
    ) -> Iterator[ChargeData]:
        """
        List charges from a connected Stripe account.

        Args:
            stripe_account_id: Connected account ID (stripe_user_id)
            starting_after: Charge ID for pagination (optional)
            limit: Number of charges per page (default: 100, max: 100)

        Yields:
            ChargeData objects for each charge

        Example:
            for charge in service.list_charges(account_id):
                print(f"Charge {charge.id}: ${charge.amount_cents / 100}")
        """
        try:
            params = {"limit": min(limit, 100)}
            if starting_after:
                params["starting_after"] = starting_after

            response = self.client.v1.charges.list(
                params=params,
                options={"stripe_account": stripe_account_id},
            )

            for charge in response.data:
                yield ChargeData(
                    id=charge.id,
                    amount_cents=charge.amount,
                    currency=charge.currency,
                    customer_id=charge.customer,
                    status=charge.status,
                    description=charge.description,
                    receipt_url=charge.receipt_url,
                    created=datetime.fromtimestamp(charge.created, tz=timezone.utc),
                )

            # Handle pagination
            while response.has_more:
                last_id = response.data[-1].id
                response = self.client.v1.charges.list(
                    params={"limit": min(limit, 100), "starting_after": last_id},
                    options={"stripe_account": stripe_account_id},
                )
                for charge in response.data:
                    yield ChargeData(
                        id=charge.id,
                        amount_cents=charge.amount,
                        currency=charge.currency,
                        customer_id=charge.customer,
                        status=charge.status,
                        description=charge.description,
                        receipt_url=charge.receipt_url,
                        created=datetime.fromtimestamp(charge.created, tz=timezone.utc),
                    )

        except Exception as e:
            logger.error(f"Failed to list charges for {stripe_account_id}: {e}")
            raise StripeConnectError(f"Failed to list charges: {e}") from e

    def list_payment_intents(
        self,
        stripe_account_id: str,
        starting_after: str | None = None,
        limit: int = 100,
    ) -> Iterator[ChargeData]:
        """
        List payment intents from a connected Stripe account.

        PaymentIntents are the modern way Stripe processes payments.
        Payment Links, Checkout Sessions, and Subscriptions all create PaymentIntents.

        Args:
            stripe_account_id: Connected account ID (stripe_user_id)
            starting_after: PaymentIntent ID for pagination (optional)
            limit: Number of payment intents per page (default: 100, max: 100)

        Yields:
            ChargeData objects for each succeeded payment intent
        """
        try:
            params = {"limit": min(limit, 100)}
            if starting_after:
                params["starting_after"] = starting_after

            response = self.client.v1.payment_intents.list(
                params=params,
                options={"stripe_account": stripe_account_id},
            )

            for pi in response.data:
                # Only yield succeeded payments
                if pi.status != "succeeded":
                    continue
                # latest_charge might be a string ID or expanded object
                receipt_url = None
                if pi.latest_charge and hasattr(pi.latest_charge, "receipt_url"):
                    receipt_url = pi.latest_charge.receipt_url
                yield ChargeData(
                    id=pi.id,
                    amount_cents=pi.amount,
                    currency=pi.currency,
                    customer_id=pi.customer,
                    status=pi.status,
                    description=pi.description,
                    receipt_url=receipt_url,
                    created=datetime.fromtimestamp(pi.created, tz=timezone.utc),
                    source_type="payment_intent",
                )

            # Handle pagination
            while response.has_more:
                last_id = response.data[-1].id
                response = self.client.v1.payment_intents.list(
                    params={"limit": min(limit, 100), "starting_after": last_id},
                    options={"stripe_account": stripe_account_id},
                )
                for pi in response.data:
                    if pi.status != "succeeded":
                        continue
                    # latest_charge might be a string ID or expanded object
                    receipt_url = None
                    if pi.latest_charge and hasattr(pi.latest_charge, "receipt_url"):
                        receipt_url = pi.latest_charge.receipt_url
                    yield ChargeData(
                        id=pi.id,
                        amount_cents=pi.amount,
                        currency=pi.currency,
                        customer_id=pi.customer,
                        status=pi.status,
                        description=pi.description,
                        receipt_url=receipt_url,
                        created=datetime.fromtimestamp(pi.created, tz=timezone.utc),
                        source_type="payment_intent",
                    )

        except Exception as e:
            logger.error(f"Failed to list payment intents for {stripe_account_id}: {e}")
            raise StripeConnectError(f"Failed to list payment intents: {e}") from e

    def list_all_payments(
        self,
        stripe_account_id: str,
        limit: int = 100,
    ) -> Iterator[ChargeData]:
        """
        List all payments from a connected account.

        Uses only the Charges API since all successful PaymentIntents create
        a corresponding Charge. This prevents duplication from the same payment
        appearing as both a Charge (ch_xxx) and PaymentIntent (pi_xxx).

        Note: The list_payment_intents() method is still available for cases
        where PaymentIntent-specific data is needed (e.g., pending payments).

        Args:
            stripe_account_id: Connected account ID (stripe_user_id)
            limit: Number per page (default: 100)

        Yields:
            ChargeData objects for each payment
        """
        charge_count = 0

        logger.info(f"Fetching charges from account {stripe_account_id}")
        for charge in self.list_charges(stripe_account_id, limit=limit):
            charge_count += 1
            yield charge

        logger.info(f"Found {charge_count} charges")

    def get_customer(self, stripe_account_id: str, customer_id: str) -> dict | None:
        """
        Retrieve customer details from a connected account.

        Args:
            stripe_account_id: Connected account ID
            customer_id: Stripe customer ID

        Returns:
            Customer data dict or None if not found

        Example:
            customer = service.get_customer(account_id, "cus_123")
            if customer:
                print(customer['email'])
        """
        try:
            customer = self.client.v1.customers.retrieve(
                customer_id,
                options={"stripe_account": stripe_account_id},
            )

            return {
                "id": customer.id,
                "email": customer.email,
                "name": customer.name,
                "phone": customer.phone,
                "description": customer.description,
                "metadata": customer.metadata,
            }
        except Exception as e:
            logger.warning(
                f"Failed to retrieve customer {customer_id} from {stripe_account_id}: {e}"
            )
            return None


# Singleton instance for convenience
_stripe_service_instance: StripeConnectService | None = None


def get_stripe_service() -> StripeConnectService:
    """Get or create the singleton Stripe Connect service instance."""
    global _stripe_service_instance
    if _stripe_service_instance is None:
        _stripe_service_instance = StripeConnectService()
    return _stripe_service_instance
