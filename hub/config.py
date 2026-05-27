from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://linkEdge:changeme@localhost:5432/linkEdge"
    )

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")

    # MQTT
    mqtt_host: str = Field(default="localhost")
    mqtt_port: int = Field(default=1883)
    mqtt_username: str = Field(default="")
    mqtt_password: str = Field(default="")
    mqtt_uplink_topic: str = Field(
        default="application/+/device/+/event/up",
        description="ChirpStack application uplink topic pattern",
    )

    # Security
    hub_secret_key: str = Field(default="change-me-in-production")

    # Export pipeline
    export_batch_size: int = Field(default=50)
    export_retry_interval: int = Field(default=30, description="Seconds between retry passes")

    # Misc
    log_level: str = Field(default="INFO")
    device_profiles_dir: str = Field(default="device_profiles")


settings = Settings()
