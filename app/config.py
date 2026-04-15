from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Baklava AI"
    ADMIN_USERNAME: str = "alim"
    DATABASE_PATH: str = "/data/baklava.db"
    SECRET_KEY: str = "change-me-in-production"
    OPENSHIFT_URL: str = "https://api.openshift.example.com:6443"
    OPENSHIFT_OAUTH_URL: str = "https://oauth-openshift.apps.openshift.example.com"
    OPENSHIFT_OAUTH_CLIENT_ID: str = "baklava-ai"
    OPENSHIFT_OAUTH_CLIENT_SECRET: str = "change-me"
    OPENSHIFT_OAUTH_SCOPE: str = "user:info"
    APP_URL: str = "http://localhost:8080"

    @property
    def authorize_url(self) -> str:
        return f"{self.OPENSHIFT_OAUTH_URL}/oauth/authorize"

    @property
    def token_url(self) -> str:
        return f"{self.OPENSHIFT_OAUTH_URL}/oauth/token"

    @property
    def user_api_url(self) -> str:
        return f"{self.OPENSHIFT_URL}/apis/user.openshift.io/v1/users/~"

    class Config:
        env_file = ".env"


settings = Settings()
