import os
from dataclasses import dataclass, field


def _env_csv(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    db_path: str = os.getenv("DB_PATH", "/data/app.db")
    workspace_root: str = os.getenv("WORKSPACE_ROOT", "/workspace")
    shell_allowlist: list[str] = field(
        default_factory=lambda: _env_csv(
            "SHELL_ALLOWLIST",
            "pytest,python -m pytest,npm test,npm run test,ruff check,black --check,go test,cargo test",
        )
    )
    command_timeout_s: int = int(os.getenv("COMMAND_TIMEOUT_S", "120"))
    network_enabled: bool = _env_bool("NETWORK_ENABLED", default=False)


settings = Settings()
