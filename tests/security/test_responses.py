from app.schemas.account import AccountResponse, AccountSessionResponse
from app.schemas.auth import TokenResponse


def test_response_schemas_omit_secrets():
    assert "password_hash" not in AccountResponse.model_fields
    assert "token_hash" not in AccountSessionResponse.model_fields
    assert "access_token" in TokenResponse.model_fields
    assert "password" not in TokenResponse.model_fields
