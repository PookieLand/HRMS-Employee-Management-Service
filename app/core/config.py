from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application Settings
    APP_NAME: str = "FastAPI Template"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Database Settings
    DB_NAME: str = "hrms_db"
    DB_USER: str = "root"
    DB_PASSWORD: str = "root"
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_CHARSET: str = "utf8"

    # Redis Settings
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    CACHE_TTL: int = 300

    # Kafka Settings
    KAFKA_BOOTSTRAP_SERVERS: str = "localhost:9092"
    KAFKA_ENABLED: bool = True

    # CORS Settings
    CORS_ORIGINS: str = "https://localhost,http://localhost:3000"
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS_ORIGINS from comma-separated string."""
        if isinstance(self.CORS_ORIGINS, str):
            return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
        return [self.CORS_ORIGINS]

    # Asgardeo OAuth2 Settings
    ASGARDEO_ORG: str = ""  # REQUIRED: Must be set in .env file
    ASGARDEO_CLIENT_ID: str = ""  # REQUIRED: Must be set in .env file
    JWT_AUDIENCE: str | None = None  # Optional: Set in .env if needed
    JWT_ISSUER: str | None = None  # Optional: Set in .env if needed

    @property
    def jwks_url(self) -> str:
        """Generate JWKS URL from Asgardeo organization."""
        return f"https://api.asgardeo.io/t/{self.ASGARDEO_ORG}/oauth2/jwks"

    @property
    def token_url(self) -> str:
        """Generate token endpoint URL from Asgardeo organization."""
        return f"https://api.asgardeo.io/t/{self.ASGARDEO_ORG}/oauth2/token"

    @property
    def issuer(self) -> str:
        """Get JWT issuer, fallback to token URL if not explicitly set."""
        if self.JWT_ISSUER:
            return self.JWT_ISSUER
        return self.token_url

    @property
    def database_url(self) -> str:
        """Generate MySQL database URL."""
        return f"mysql+mysqldb://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset={self.DB_CHARSET}"

    @property
    def database_url_without_db(self) -> str:
        """Generate MySQL URL without database name (for initial connection)."""
        return f"mysql+mysqldb://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}?charset={self.DB_CHARSET}"

    class Config:
        env_file = ".env"
        case_sensitive = True


# Create global settings instance
settings = Settings()
