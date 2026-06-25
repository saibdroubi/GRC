from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://saibdroubi@localhost:5432/grc_dev"
    anthropic_api_key: str = ""

    # Master key for encrypting IntegrationConnection config (credentials for
    # M365, Nessus, Palo Alto, Burp, etc.) at rest in Postgres. Generate with:
    # python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    secret_encryption_key: str = ""

    # Embeddings provider for the knowledge base (pgvector-backed). Anthropic
    # has no embeddings API; Voyage AI is its recommended partner.
    voyage_api_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
