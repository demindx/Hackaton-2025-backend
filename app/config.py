from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    openai_api_key: str = Field()


    model_config = SettingsConfigDict(env_file=".env")


config = Config()
