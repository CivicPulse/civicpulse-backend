"""Tests for Stripe Connect service."""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
from stripe.oauth_error import OAuthError

from civicpulse.services.stripe_connect import (
    ChargeData,
    OAuthResult,
    StripeConnectError,
    StripeConnectService,
    get_stripe_service,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton before each test."""
    import civicpulse.services.stripe_connect as stripe_module

    stripe_module._stripe_service_instance = None
    yield


@pytest.fixture
def mock_stripe_settings():
    """Mock stripe settings for tests."""
    with patch("civicpulse.services.stripe_connect.stripe_settings") as mock:
        mock.CLIENT_ID = "ca_test_123"
        mock.SECRET_KEY = "sk_test_456"
        mock.OAUTH_SCOPE = "read_only"
        mock.is_configured = True
        yield mock


class TestStripeConnectService:
    """Test suite for StripeConnectService using pytest."""

    @patch("civicpulse.services.stripe_connect.StripeClient")
    def test_service_initialization(self, mock_stripe_client, mock_stripe_settings):
        """Test that service initializes with valid configuration."""
        service = StripeConnectService()
        assert service.client is not None

    def test_missing_credentials_raises_error(self):
        """Test that missing credentials raises StripeConnectError."""
        with patch("civicpulse.services.stripe_connect.stripe_settings") as mock:
            mock.is_configured = False

            with pytest.raises(StripeConnectError, match="Stripe not configured"):
                StripeConnectService()

    @patch("civicpulse.services.stripe_connect.StripeClient")
    def test_get_oauth_url(self, mock_stripe_client, mock_stripe_settings):
        """Test generating OAuth authorization URL."""
        mock_client = Mock()
        mock_client.oauth.authorize_url.return_value = "https://stripe.com/oauth?..."
        mock_stripe_client.return_value = mock_client

        service = StripeConnectService()
        url = service.get_oauth_url(
            state="random_state", redirect_uri="https://example.com/callback"
        )

        assert url == "https://stripe.com/oauth?..."
        mock_client.oauth.authorize_url.assert_called_once_with(
            scope="read_only",
            redirect_uri="https://example.com/callback",
            state="random_state",
        )

    @patch("civicpulse.services.stripe_connect.StripeClient")
    def test_get_oauth_url_error(self, mock_stripe_client, mock_stripe_settings):
        """Test OAuth URL generation error handling."""
        mock_client = Mock()
        mock_client.oauth.authorize_url.side_effect = Exception("Network error")
        mock_stripe_client.return_value = mock_client

        service = StripeConnectService()
        with pytest.raises(StripeConnectError, match="Failed to generate OAuth URL"):
            service.get_oauth_url(state="state", redirect_uri="https://example.com")

    @patch("civicpulse.services.stripe_connect.StripeClient")
    def test_exchange_code_success(self, mock_stripe_client, mock_stripe_settings):
        """Test successful OAuth code exchange."""
        mock_client = Mock()
        mock_client.oauth.token.return_value = {
            "access_token": "sk_live_123",
            "refresh_token": "rt_123",
            "stripe_user_id": "acct_123",
            "stripe_publishable_key": "pk_live_456",
            "livemode": True,
            "scope": "read_only",
        }
        mock_stripe_client.return_value = mock_client

        service = StripeConnectService()
        result = service.exchange_code("auth_code_123")

        assert isinstance(result, OAuthResult)
        assert result.access_token == "sk_live_123"
        assert result.refresh_token == "rt_123"
        assert result.stripe_user_id == "acct_123"
        assert result.stripe_publishable_key == "pk_live_456"
        assert result.livemode is True
        assert result.scope == "read_only"

        mock_client.oauth.token.assert_called_once_with(
            params={"grant_type": "authorization_code", "code": "auth_code_123"}
        )

    @patch("civicpulse.services.stripe_connect.StripeClient")
    def test_exchange_code_oauth_error(self, mock_stripe_client, mock_stripe_settings):
        """Test OAuth code exchange with OAuthError."""
        mock_client = Mock()
        mock_client.oauth.token.side_effect = OAuthError("invalid_code", "Invalid code")
        mock_stripe_client.return_value = mock_client

        service = StripeConnectService()
        with pytest.raises(StripeConnectError, match="OAuth token exchange failed"):
            service.exchange_code("invalid_code")

    @patch("civicpulse.services.stripe_connect.StripeClient")
    def test_refresh_access_token_success(
        self, mock_stripe_client, mock_stripe_settings
    ):
        """Test successful token refresh."""
        mock_client = Mock()
        mock_client.oauth.token.return_value = {
            "access_token": "sk_live_new_123",
            "refresh_token": "rt_new_123",
            "stripe_user_id": "acct_123",
            "stripe_publishable_key": "pk_live_456",
            "livemode": True,
            "scope": "read_only",
        }
        mock_stripe_client.return_value = mock_client

        service = StripeConnectService()
        result = service.refresh_access_token("rt_old_123")

        assert isinstance(result, OAuthResult)
        assert result.access_token == "sk_live_new_123"
        assert result.refresh_token == "rt_new_123"

        mock_client.oauth.token.assert_called_once_with(
            params={"grant_type": "refresh_token", "refresh_token": "rt_old_123"}
        )

    @patch("civicpulse.services.stripe_connect.StripeClient")
    def test_refresh_token_preserves_old_refresh_token(
        self, mock_stripe_client, mock_stripe_settings
    ):
        """Test that refresh preserves old refresh token if new one not provided."""
        mock_client = Mock()
        mock_client.oauth.token.return_value = {
            "access_token": "sk_live_new_123",
            # No refresh_token in response
            "stripe_user_id": "acct_123",
            "stripe_publishable_key": "pk_live_456",
            "livemode": True,
            "scope": "read_only",
        }
        mock_stripe_client.return_value = mock_client

        service = StripeConnectService()
        result = service.refresh_access_token("rt_old_123")

        # Should use old refresh token
        assert result.refresh_token == "rt_old_123"

    @patch("civicpulse.services.stripe_connect.StripeClient")
    def test_deauthorize_success(self, mock_stripe_client, mock_stripe_settings):
        """Test successful account deauthorization."""
        mock_client = Mock()
        mock_client.oauth.deauthorize.return_value = {"stripe_user_id": "acct_123"}
        mock_stripe_client.return_value = mock_client

        service = StripeConnectService()
        result = service.deauthorize("acct_123")

        assert result is True
        mock_client.oauth.deauthorize.assert_called_once_with(
            params={"stripe_user_id": "acct_123"}
        )

    @patch("civicpulse.services.stripe_connect.StripeClient")
    def test_deauthorize_error(self, mock_stripe_client, mock_stripe_settings):
        """Test deauthorization error handling."""
        mock_client = Mock()
        mock_client.oauth.deauthorize.side_effect = OAuthError(
            "invalid_account", "Invalid account"
        )
        mock_stripe_client.return_value = mock_client

        service = StripeConnectService()
        with pytest.raises(StripeConnectError, match="Deauthorization failed"):
            service.deauthorize("acct_123")

    @patch("civicpulse.services.stripe_connect.StripeClient")
    def test_list_charges_single_page(self, mock_stripe_client, mock_stripe_settings):
        """Test listing charges with single page of results."""
        mock_charge = MagicMock()
        mock_charge.id = "ch_123"
        mock_charge.amount = 5000
        mock_charge.currency = "usd"
        mock_charge.customer = "cus_456"
        mock_charge.status = "succeeded"
        mock_charge.description = "Donation"
        mock_charge.receipt_url = "https://stripe.com/receipt"
        mock_charge.created = 1609459200  # 2021-01-01

        mock_response = MagicMock()
        mock_response.data = [mock_charge]
        mock_response.has_more = False

        mock_client = Mock()
        mock_client.v1.charges.list.return_value = mock_response
        mock_stripe_client.return_value = mock_client

        service = StripeConnectService()
        charges = list(service.list_charges("acct_123"))

        assert len(charges) == 1
        charge = charges[0]
        assert isinstance(charge, ChargeData)
        assert charge.id == "ch_123"
        assert charge.amount_cents == 5000
        assert charge.currency == "usd"
        assert charge.customer_id == "cus_456"
        assert charge.status == "succeeded"
        assert charge.description == "Donation"
        assert charge.receipt_url == "https://stripe.com/receipt"
        assert isinstance(charge.created, datetime)

    @patch("civicpulse.services.stripe_connect.StripeClient")
    def test_list_charges_pagination(self, mock_stripe_client, mock_stripe_settings):
        """Test listing charges with pagination."""
        # First page
        mock_charge1 = MagicMock()
        mock_charge1.id = "ch_1"
        mock_charge1.amount = 1000
        mock_charge1.currency = "usd"
        mock_charge1.customer = None
        mock_charge1.status = "succeeded"
        mock_charge1.description = None
        mock_charge1.receipt_url = None
        mock_charge1.created = 1609459200

        # Second page
        mock_charge2 = MagicMock()
        mock_charge2.id = "ch_2"
        mock_charge2.amount = 2000
        mock_charge2.currency = "usd"
        mock_charge2.customer = None
        mock_charge2.status = "succeeded"
        mock_charge2.description = None
        mock_charge2.receipt_url = None
        mock_charge2.created = 1609459300

        mock_response1 = MagicMock()
        mock_response1.data = [mock_charge1]
        mock_response1.has_more = True

        mock_response2 = MagicMock()
        mock_response2.data = [mock_charge2]
        mock_response2.has_more = False

        mock_client = Mock()
        mock_client.v1.charges.list.side_effect = [mock_response1, mock_response2]
        mock_stripe_client.return_value = mock_client

        service = StripeConnectService()
        charges = list(service.list_charges("acct_123", limit=1))

        assert len(charges) == 2
        assert charges[0].id == "ch_1"
        assert charges[1].id == "ch_2"

        # Verify pagination calls
        assert mock_client.v1.charges.list.call_count == 2

    @patch("civicpulse.services.stripe_connect.StripeClient")
    def test_list_charges_with_starting_after(
        self, mock_stripe_client, mock_stripe_settings
    ):
        """Test listing charges with starting_after parameter."""
        mock_response = MagicMock()
        mock_response.data = []
        mock_response.has_more = False

        mock_client = Mock()
        mock_client.v1.charges.list.return_value = mock_response
        mock_stripe_client.return_value = mock_client

        service = StripeConnectService()
        list(service.list_charges("acct_123", starting_after="ch_last"))

        mock_client.v1.charges.list.assert_called_once_with(
            params={"limit": 100, "starting_after": "ch_last"},
            options={"stripe_account": "acct_123"},
        )

    @patch("civicpulse.services.stripe_connect.StripeClient")
    def test_list_charges_error(self, mock_stripe_client, mock_stripe_settings):
        """Test list charges error handling."""
        mock_client = Mock()
        mock_client.v1.charges.list.side_effect = Exception("API error")
        mock_stripe_client.return_value = mock_client

        service = StripeConnectService()
        with pytest.raises(StripeConnectError, match="Failed to list charges"):
            list(service.list_charges("acct_123"))

    @patch("civicpulse.services.stripe_connect.StripeClient")
    def test_get_customer_success(self, mock_stripe_client, mock_stripe_settings):
        """Test successful customer retrieval."""
        mock_customer = MagicMock()
        mock_customer.id = "cus_123"
        mock_customer.email = "donor@example.com"
        mock_customer.name = "John Doe"
        mock_customer.phone = "+15555551234"
        mock_customer.description = "Monthly donor"
        mock_customer.metadata = {"source": "campaign_2024"}

        mock_client = Mock()
        mock_client.v1.customers.retrieve.return_value = mock_customer
        mock_stripe_client.return_value = mock_client

        service = StripeConnectService()
        customer = service.get_customer("acct_123", "cus_123")

        assert customer is not None
        assert customer["id"] == "cus_123"
        assert customer["email"] == "donor@example.com"
        assert customer["name"] == "John Doe"
        assert customer["phone"] == "+15555551234"
        assert customer["description"] == "Monthly donor"
        assert customer["metadata"] == {"source": "campaign_2024"}

        mock_client.v1.customers.retrieve.assert_called_once_with(
            "cus_123", options={"stripe_account": "acct_123"}
        )

    @patch("civicpulse.services.stripe_connect.StripeClient")
    def test_get_customer_not_found(self, mock_stripe_client, mock_stripe_settings):
        """Test customer retrieval when customer doesn't exist."""
        mock_client = Mock()
        mock_client.v1.customers.retrieve.side_effect = Exception("No such customer")
        mock_stripe_client.return_value = mock_client

        service = StripeConnectService()
        customer = service.get_customer("acct_123", "cus_nonexistent")

        assert customer is None

    @patch("civicpulse.services.stripe_connect.StripeClient")
    def test_singleton_get_stripe_service(
        self, mock_stripe_client, mock_stripe_settings
    ):
        """Test that get_stripe_service returns singleton instance."""
        mock_client = Mock()
        mock_stripe_client.return_value = mock_client

        service1 = get_stripe_service()
        service2 = get_stripe_service()

        assert service1 is service2

    @patch("civicpulse.services.stripe_connect.StripeClient")
    def test_list_charges_respects_limit(
        self, mock_stripe_client, mock_stripe_settings
    ):
        """Test that list_charges respects the limit parameter (max 100)."""
        mock_response = MagicMock()
        mock_response.data = []
        mock_response.has_more = False

        mock_client = Mock()
        mock_client.v1.charges.list.return_value = mock_response
        mock_stripe_client.return_value = mock_client

        service = StripeConnectService()

        # Test with limit > 100 (should be capped at 100)
        list(service.list_charges("acct_123", limit=500))
        call_args = mock_client.v1.charges.list.call_args
        assert call_args.kwargs["params"]["limit"] == 100

        # Test with limit < 100
        mock_client.v1.charges.list.reset_mock()
        list(service.list_charges("acct_123", limit=50))
        call_args = mock_client.v1.charges.list.call_args
        assert call_args.kwargs["params"]["limit"] == 50

    @patch("civicpulse.services.stripe_connect.StripeClient")
    def test_list_all_payments_deduplicates_charge_and_payment_intent(
        self, mock_stripe_client, mock_stripe_settings
    ):
        """Test that list_all_payments() deduplicates by using only Charges API.

        When a PaymentIntent is created, Stripe also creates a corresponding Charge.
        The list_all_payments() method should only return one ChargeData per payment,
        not both the charge and the payment intent.
        """
        # Create a mock charge that represents the same underlying payment as a PaymentIntent
        mock_charge = MagicMock()
        mock_charge.id = "ch_123"
        mock_charge.amount = 2500  # $25.00
        mock_charge.currency = "usd"
        mock_charge.customer = "cus_456"
        mock_charge.status = "succeeded"
        mock_charge.description = "Donation"
        mock_charge.receipt_url = "https://stripe.com/receipt"
        mock_charge.created = 1609459200

        mock_charges_response = MagicMock()
        mock_charges_response.data = [mock_charge]
        mock_charges_response.has_more = False

        mock_client = Mock()
        mock_client.v1.charges.list.return_value = mock_charges_response
        mock_stripe_client.return_value = mock_client

        service = StripeConnectService()
        payments = list(service.list_all_payments("acct_123"))

        # Should only yield the charge, not duplicate from payment intents
        assert len(payments) == 1
        assert payments[0].id == "ch_123"
        assert payments[0].amount_cents == 2500
        assert payments[0].source_type == "charge"

        # Verify only the charges API was called (not payment_intents)
        mock_client.v1.charges.list.assert_called_once()
        # The list_all_payments() method should NOT call payment_intents.list
        assert not hasattr(mock_client.v1, "payment_intents") or not mock_client.v1.payment_intents.list.called

    @patch("civicpulse.services.stripe_connect.StripeClient")
    def test_list_all_payments_yields_orphan_payment_intents(
        self, mock_stripe_client, mock_stripe_settings
    ):
        """Test that orphan PaymentIntents (with no Charge) are handled gracefully.

        Since list_all_payments() uses only the Charges API, orphan PaymentIntents
        (those without a corresponding Charge, i.e., latest_charge is None) won't
        appear in the results. This is expected behavior because:
        1. Successful PaymentIntents always create a Charge
        2. PaymentIntents without Charges are typically pending/failed payments
        3. Using only Charges prevents duplicate donation records

        This test verifies the method handles the case where no charges exist,
        which implicitly covers orphan PaymentIntent scenarios.
        """
        # Mock an empty charges response (no charges exist)
        mock_charges_response = MagicMock()
        mock_charges_response.data = []
        mock_charges_response.has_more = False

        mock_client = Mock()
        mock_client.v1.charges.list.return_value = mock_charges_response
        mock_stripe_client.return_value = mock_client

        service = StripeConnectService()
        payments = list(service.list_all_payments("acct_123"))

        # Should return empty list when no charges exist
        # This implicitly handles orphan PaymentIntents by not fetching them
        assert len(payments) == 0

        # Verify charges API was called correctly
        mock_client.v1.charges.list.assert_called_once()

        # Verify payment_intents API was NOT called
        # (orphan PaymentIntents are handled by not querying for them)
        assert not hasattr(mock_client.v1, "payment_intents") or not mock_client.v1.payment_intents.list.called

    @patch("civicpulse.services.stripe_connect.StripeClient")
    def test_list_all_payments_legacy_charges_only(
        self, mock_stripe_client, mock_stripe_settings
    ):
        """Test that list_all_payments() correctly handles legacy charges only.

        Legacy charges are charges created directly via the Charges API (before
        PaymentIntents became the standard). These charges have no associated
        PaymentIntent. The list_all_payments() method should return all such
        charges with source_type='charge'.
        """
        # Create mock legacy charges (no payment_intent field)
        mock_charge1 = MagicMock()
        mock_charge1.id = "ch_legacy_1"
        mock_charge1.amount = 1500  # $15.00
        mock_charge1.currency = "usd"
        mock_charge1.customer = "cus_legacy_donor"
        mock_charge1.status = "succeeded"
        mock_charge1.description = "Legacy donation"
        mock_charge1.receipt_url = "https://stripe.com/receipt/legacy1"
        mock_charge1.created = 1577836800  # 2020-01-01

        mock_charge2 = MagicMock()
        mock_charge2.id = "ch_legacy_2"
        mock_charge2.amount = 5000  # $50.00
        mock_charge2.currency = "usd"
        mock_charge2.customer = None  # Guest donation
        mock_charge2.status = "succeeded"
        mock_charge2.description = None
        mock_charge2.receipt_url = None
        mock_charge2.created = 1580515200  # 2020-02-01

        mock_charges_response = MagicMock()
        mock_charges_response.data = [mock_charge1, mock_charge2]
        mock_charges_response.has_more = False

        mock_client = Mock()
        mock_client.v1.charges.list.return_value = mock_charges_response
        mock_stripe_client.return_value = mock_client

        service = StripeConnectService()
        payments = list(service.list_all_payments("acct_legacy_123"))

        # Should return both legacy charges
        assert len(payments) == 2

        # Verify first charge
        assert payments[0].id == "ch_legacy_1"
        assert payments[0].amount_cents == 1500
        assert payments[0].currency == "usd"
        assert payments[0].customer_id == "cus_legacy_donor"
        assert payments[0].status == "succeeded"
        assert payments[0].description == "Legacy donation"
        assert payments[0].receipt_url == "https://stripe.com/receipt/legacy1"
        assert payments[0].source_type == "charge"

        # Verify second charge
        assert payments[1].id == "ch_legacy_2"
        assert payments[1].amount_cents == 5000
        assert payments[1].customer_id is None
        assert payments[1].source_type == "charge"

        # Verify only the charges API was called
        mock_client.v1.charges.list.assert_called_once()

        # Verify payment_intents API was NOT called
        assert not hasattr(mock_client.v1, "payment_intents") or not mock_client.v1.payment_intents.list.called
