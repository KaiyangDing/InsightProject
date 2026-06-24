"""项目统一配置中心。"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pydantic import SecretStr


class Settings(BaseSettings):
    # 告诉 pydantic-settings：也从 .env 文件读（系统环境变量优先级更高）。
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # .env 里有多余变量时忽略，不报错
    )

    # 字段名小写，会自动匹配同名大写环境变量（DASHSCOPE_API_KEY 等），大小写不敏感。
    dashscope_api_key: SecretStr  # 必填，无默认值
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    chat_model: str = "qwen-plus"
    db_path: str = "data/olist.db"  # SQLite 示例库路径（相对项目根）
    # 以后会往这里加：embedding_model、rerank_model、各档位模型、预算上限 等


@lru_cache
def get_settings() -> Settings:
    """返回全局唯一配置实例（懒加载，全程只构造一次）。"""
    return Settings()
