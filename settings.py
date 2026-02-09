from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Asistente de Negocio API"
    DEBUG: bool = True


settings = Settings()
