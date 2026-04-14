import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    项目配置对象。

    BaseSettings 会在实例化时自动读取环境变量和 `.env` 文件，
    所以业务代码里只需要 `from config.settings import settings`，
    不需要每个文件都自己手写读取 `.env` 的逻辑。
    """

    API_KEY: str = os.environ.get("API_KEY")
    BASE_URL: str = os.environ.get("BASE_URL")
    MODEL: str = os.environ.get("MODEL")
    EMBEDDING_MODEL: str = os.environ.get("EMBEDDING_MODEL")

    KNOWLEDGE_BASE_URL: str = os.environ.get("KNOWLEDGE_BASE_URL")

    _current_dir = os.path.dirname(os.path.abspath(__file__))
    _project_root = os.path.dirname(_current_dir)

    VECTOR_STORE_PATH: str = os.path.join(_project_root, "chroma_kb1")
    CRAWL_OUTPUT_DIR: str = os.path.join(_project_root, "data", "crawl")
    MD_FOLDER_PATH: str = CRAWL_OUTPUT_DIR
    TMP_MD_FOLDER_PATH: str = os.path.join(_project_root, "data", "tmp")

    CHUNK_SIZE: int = 3000
    CHUNK_OVERLAP: int = 200

    TOP_ROUGH: int = 50
    TOP_FINAL: int = 5

    model_config = SettingsConfigDict(
        env_file=os.path.join(_project_root, ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


# 只实例化一次，其他模块直接复用这一份配置。
settings = Settings()
