"""Application configuration, read from the environment and nowhere else.

There are deliberately no defaults for the connection strings: a service that silently
falls back to ``localhost`` when its configuration is missing fails in production
looking like a network problem instead of a config problem. Missing configuration
should stop the process at startup, loudly.

Settings objects are frozen (coding rule 13) so no request handler can mutate them.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the API service.

    The URL must point at the read-only application role. The service holds no
    credentials that can write; that is enforced by PostgreSQL grants, not by this
    class, but pointing it at an owner role would defeat the arrangement.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", frozen=True)

    database_url: str = Field(
        description="SQLAlchemy URL for the read-only application role.",
    )
    cors_allow_origins: str = Field(
        default="",
        description=(
            "Comma-separated browser origins allowed by CORS. Empty means no CORS "
            "middleware at all: same-origin deployments (nginx in front) need none."
        ),
    )


class LlmSettings(BaseSettings):
    """Which model answers questions, and the credential that reaches it.

    Separate from :class:`Settings` so the seeder and any future component that needs a
    database but no model cannot pull a required API key into their startup path.

    The key is a :class:`SecretStr`: printing the settings object, logging it, or letting
    it surface in a traceback all yield ``**********`` rather than the credential. There is
    no default, so a missing key stops the process at startup instead of producing a
    service that 401s on the customer's first question.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", frozen=True)

    anthropic_api_key: SecretStr = Field(
        description="Credential for the model provider. Never logged, never committed.",
    )
    llm_model: str = Field(
        description=(
            "The one value that selects a provider, in init_chat_model's "
            "'provider:model' form. Pinned to a dated model id, never an alias."
        ),
    )
    llm_timeout_seconds: float = Field(
        default=25.0,
        description="Per-call ceiling, chosen to stay inside the chat route's 30 s budget.",
    )


class SeedSettings(BaseSettings):
    """Configuration for the one-shot seeder.

    Separate from :class:`Settings` because the seeder is the only component that
    connects as the owning role. Keeping the two URLs in different objects means the
    API cannot accidentally pick up write credentials.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", frozen=True)

    seed_database_url: str = Field(
        description="SQLAlchemy URL for the owning role used to create and load tables.",
    )
    dataset_path: Path = Field(
        description="Absolute path to the source CSV.",
    )
    read_only_role: str = Field(
        description="Database role the API connects as; granted SELECT on the seeded table.",
    )
