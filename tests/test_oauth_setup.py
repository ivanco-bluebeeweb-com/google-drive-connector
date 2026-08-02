import pytest

import handlers
from imperal_sdk.testing import MockSecretStore
from models import NoParams


@pytest.mark.asyncio
async def test_connect_reports_missing_app_oauth_credentials_before_redirect(ctx):
    ctx.secrets = MockSecretStore()

    result = await handlers.connect_google_drive(ctx, NoParams())

    assert result.status == "error"
    assert result.error_code == "GOOGLE_OAUTH_NOT_CONFIGURED"
    assert "client ID and client secret" in result.error
