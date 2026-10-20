"""Central typed settings — one source of truth for env config.

`models/database.py` remains the data-file layer (config.json, DATA_DIR);
this module types the *process* config (bind, CORS, model names) so new
code stops scattering os.environ reads. Migrate readers gradually.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    # Network
    aria_host: str = "127.0.0.1"
    aria_port: int = 8000
    aria_cors_origins: str = (
        "http://localhost:5173,http://localhost:4173,http://localhost:3000,"
        "http://127.0.0.1:5173,http://127.0.0.1:4173"
    )
    ollama_url: str = "http://127.0.0.1:11434"
    # Shared/published servers only: when set, non-loopback /api callers
    # must send `Authorization: Bearer <token>`. Localhost is always exempt.
    aria_api_token: str = ""

    # Models (single source of truth is models.database.MODELS)
    aria_main_model: str = "qwen3.5:9b"
    aria_embed_model: str = "nomic-embed-text"

    # Cloud providers — OFF by default: ARIA's promise is local-only AI.
    # Requires BOTH a credential (ANTHROPIC_API_KEY) and explicit consent
    # (ARIA_CLOUD_CONSENT=1) because enabling it sends student content to
    # Anthropic. See docs/PROVIDERS.md.
    anthropic_api_key: str = ""
    aria_cloud_consent: bool = False
    # Cloud gateway (deploy/gateway): when ARIA_GATEWAY_URL is set, ALL
    # Anthropic traffic routes through the Cloud Boost gateway instead of
    # api.anthropic.com. The gateway holds the real API key; the backend
    # authenticates with a gateway token (gw_…). Consent is still required
    # — the gateway forwards student content to Anthropic. The gateway's
    # dollar-float metering ledger is the OPERATOR's cost meter; ARIA's
    # microdollar wallet is the per-student prepaid credit — both run.
    aria_gateway_url: str = ""
    aria_gateway_token: str = ""
    # Pricing (USD per million tokens) — used for cost estimates in the usage
    # ledger. Anthropic base prices per platform.claude.com/docs
    # (verified 2026-10): Haiku 5.5 $0.10/$0.50. Override via env.
    aria_price_input_mtok: float = 0.0  # local Ollama inference is free
    aria_price_output_mtok: float = 0.0
    anthropic_price_input_mtok: float = 0.10
    anthropic_price_output_mtok: float = 0.50

    # Research: TLS-verify fallback for school/corporate proxies (Zscaler).
    # Default False = verify=True first; only on SSLError retry verify=False
    # (existing behaviour, logged). Set ARIA_SEARCH_STRICT_TLS=1 to never
    # downgrade — the request fails instead.
    search_strict_tls: bool = True
    # TLS-verified search by default. On school/corporate networks with
    # TLS-intercepting proxies (Zscaler), set ARIA_SEARCH_STRICT_TLS=0 to
    # re-enable the unverified fallback — web results feed the tutor prompt,
    # so a MITM could otherwise inject fake "search results".

    # Student
    student_name: str = "Student"
    aria_student_age: int = 13

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.aria_cors_origins.split(",") if o.strip()]


settings = Settings()
