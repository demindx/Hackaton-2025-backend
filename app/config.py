from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from openai import OpenAI


class Config(BaseSettings):
    openai_api_key: str = Field(..., env="OPENAI_API_KEY")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


config = Config()


def get_openai_client() -> OpenAI:
    return OpenAI(api_key=config.openai_api_key)
