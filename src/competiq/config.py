from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    groq_api_key: str = ""
    gemini_api_key: str = ""
    ollama_host: str = "http://localhost:11434"

    groq_model: str = "llama-3.3-70b-versatile"
    gemini_model: str = "gemini-2.0-flash-exp"
    ollama_model: str = "llama3.2:3b"

    postgres_url: str = "postgresql://competiq:competiq@localhost:5432/competiq"
    redis_url: str = "redis://localhost:6379"

    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "http://localhost:3000"

    log_level: str = "INFO"


settings = Settings()
