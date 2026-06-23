from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://saibdroubi@localhost:5432/grc_dev"
    anthropic_api_key: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
