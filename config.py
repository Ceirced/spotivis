import os

from dotenv import load_dotenv


class BaseConfig:
    load_dotenv()
    TESTING = False
    SECRET_KEY = os.getenv("SECRET_KEY")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    LOG_TO_STDOUT = os.environ.get("LOG_TO_STDOUT")
    # Preprocessed data directory path (relative to static folder)
    PREPROCESSED_DATA_DIR = "preprocessed"


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    FLASK_ENV = "development"
    SQLALCHEMY_DATABASE_URI = "sqlite:///spotivis.db"
    REDIS_URL = "redis://redis" if os.getenv("IN_CONTAINER") else "redis://localhost"
    SECURITY_PASSWORD_SALT = os.getenv("SECURITY_PASSWORD_SALT")


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///"
    FLASK_ENV = "testing"
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


class ProductionConfig(BaseConfig):
    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI")
    SESSION_COOKIE_SECURE = (
        True  # does not allow cookies to be sent over an unencrypted connection
    )
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "Strict"
    SERVER_NAME = os.getenv("HOST_NAME")
    PREFERRED_URL_SCHEME = "https"
    FLASK_ENV = "production"
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost")
