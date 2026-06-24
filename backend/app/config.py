from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://saibdroubi@localhost:5432/grc_dev"
    anthropic_api_key: str = ""

    # Entra ID (Azure AD) app registration used for the Microsoft 365 / Graph
    # adapter. Client credentials (app-only) flow — read-only Graph scopes
    # only for this first pass. The secret never touches the database; it
    # lives here (.env) only, consistent with the on-prem connector model in
    # docs/ARCHITECTURE.md.
    m365_tenant_id: str = ""
    m365_client_id: str = ""
    m365_client_secret: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
