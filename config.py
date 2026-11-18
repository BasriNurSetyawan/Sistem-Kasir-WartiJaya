import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')

class Config:
    # SQLite untuk penggunaan lokal; URI dapat diganti melalui environment.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', f"sqlite:///{BASE_DIR / 'toko_warti_jaya.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}
    # Set a persistent secret in the environment for deployments.
    SECRET_KEY = os.environ.get('SECRET_KEY')
    API_TOKEN = os.environ.get('API_TOKEN')
    BUSINESS_TIMEZONE = os.environ.get('BUSINESS_TIMEZONE', 'Asia/Jakarta')
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    BOOTSTRAP_ADMIN_USERNAME = os.environ.get('BOOTSTRAP_ADMIN_USERNAME')
    BOOTSTRAP_ADMIN_PASSWORD = os.environ.get('BOOTSTRAP_ADMIN_PASSWORD')
