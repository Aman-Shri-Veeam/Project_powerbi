import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Authentication
    powerbi_client_id: str = os.getenv("POWERBI_CLIENT_ID", "")
    powerbi_client_secret: str = os.getenv("POWERBI_CLIENT_SECRET", "")
    powerbi_tenant_id: str = os.getenv("POWERBI_TENANT_ID", "")
    
    # API Configuration
    api_base_url: str = os.getenv("API_BASE_URL", "https://api.powerbi.com/v1.0/myorg")
    resource: str = "https://analysis.windows.net/powerbi/api"
    authority_url: str = "https://login.microsoftonline.com"
    
    # Storage
    backup_path: str = os.getenv("BACKUP_PATH", "./backups")
    
    # Server
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
