from pydantic import BaseModel, Field
import os


class Settings(BaseModel):
    ollama_base_url: str = Field(default=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"))
    db_path: str = Field(default=os.getenv("DB_PATH", "/data/app.db"))
    workspace_root: str = Field(default=os.getenv("WORKSPACE_ROOT", "/workspace"))
    shell_allowlist: list[str] = Field(
        default_factory=lambda: os.getenv(
            "SHELL_ALLOWLIST",
            "pytest,python -m pytest,npm test,npm run test,ruff check,black --check,go test,cargo test",
        ).split(",")
    )
    command_timeout_s: int = Field(default=int(os.getenv("COMMAND_TIMEOUT_S", "120")))
    network_enabled: bool = Field(default=os.getenv("NETWORK_ENABLED", "false").lower() == "true")


settings = Settings()
