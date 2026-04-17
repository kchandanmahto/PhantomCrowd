from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "PhantomCrowd"
    debug: bool = False
    database_url: str = "sqlite+aiosqlite:///./data/phantomcrowd.db"

    # LLM configuration (OpenAI-compatible) — defaults to Ollama (free, local)
    llm_api_key: str = "ollama"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_model: str = "qwen2.5:7b"
    llm_analysis_model: str = "qwen2.5:7b"
    controversy_model: str = ""  # Separate model for controversy detection (uses Ollama native API)

    # Server
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    api_key: str = ""  # Set to enable API key auth (empty = auth disabled)

    # Simulation defaults
    default_audience_size: int = 50
    max_audience_size: int = 500
    batch_size: int = 10

    model_config = {"env_file": ".env", "env_prefix": "PC_"}


settings = Settings()
