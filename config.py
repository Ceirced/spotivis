import os

from dotenv import load_dotenv


class BaseConfig:
    load_dotenv()
    TESTING = False
    SECRET_KEY = os.getenv("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.getenv("SQLALCHEMY_DATABASE_URI")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    LOG_TO_STDOUT = os.environ.get("LOG_TO_STDOUT")
    SERVER_NAME = os.getenv("HOST_NAME")
    SECURITY_PASSWORD_SALT = os.getenv("SECURITY_PASSWORD_SALT")


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    FLASK_ENV = "development"
    REDIS_URL = "redis://redis" if os.getenv("IN_CONTAINER") else "redis://localhost"


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///"
    FLASK_ENV = "testing"
    REDIS_URL = "redis://localhost"


class ProductionConfig(BaseConfig):
    SESSION_COOKIE_SECURE = (
        True  # does not allow cookies to be sent over an unencrypted connection
    )
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = "Strict"
    PREFERRED_URL_SCHEME = "https"
    FLASK_ENV = "production"
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost")
