from pydantic_settings import BaseSettings

class Config(BaseSettings):
    openai_api_key: str
    serper_api_key: str

    class Config:
        env_file = ".env"

config = Config()
