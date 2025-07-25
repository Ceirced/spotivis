import os
from dotenv import load_dotenv


class BaseConfig:
    load_dotenv()
    TESTING = False
    SECRET_KEY = os.getenv("SECRET_KEY")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    LOG_TO_STDOUT = os.environ.get("LOG_TO_STDOUT")


class MigrateConfig(BaseConfig):
    load_dotenv()
    DEBUG = True
    SECRET_KEY = os.getenv("SECRET_KEY")
    FLASK_ENV = "development"
    SQLALCHEMY_DATABASE_URI = os.getenv("DEV_DB_URI")


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SECRET_KEY = os.getenv("SECRET_KEY")
    FLASK_ENV = "development"
    SQLALCHEMY_DATABASE_URI = "sqlite:///dev.db"
    SERVER_NAME = os.getenv("HOST_NAME")
    REDIS_URL = "redis://localhost"


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///"
    SECRET_KEY = os.getenv("SECRET_KEY")
    FLASK_ENV = "testing"


class ProductionConfig(BaseConfig):
    SECRET_KEY = os.getenv("SECRET_KEY")
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


class LocalConfig(BaseConfig):
    load_dotenv()
    DEBUG = True
    SECRET_KEY = os.getenv("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.getenv("LOCAL_DATABASE_URI")
