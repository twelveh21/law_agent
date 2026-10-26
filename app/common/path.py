import os
from pathlib import Path

from dotenv import load_dotenv

# 当前文件位于 app/common/path.py：
# parents[0] 是 common，parents[1] 是 app，parents[2] 是项目根目录。
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

# 从项目根目录读取 .env，不依赖启动程序时所在的目录。
load_dotenv(ENV_FILE)

def _configured_path(env_name: str, default_path: Path) -> Path:
    """读取路径配置；相对路径以项目根目录为基准。"""
    value = os.getenv(env_name)
    configured_path = Path(value).expanduser() if value else default_path
    if not configured_path.is_absolute():
        configured_path = PROJECT_ROOT / configured_path
    return configured_path.resolve()


# 路径集中配置。环境变量可以覆盖默认值；相对值也统一相对项目根目录。
DATA_DIR = _configured_path("LAW_DATA_DIR", PROJECT_ROOT / "data")
DATABASE_PATH = _configured_path(
    "LAW_DATABASE_PATH", PROJECT_ROOT / "db" / "law.db"
)
CHROMA_DIR = _configured_path("CHROMA_PATH", PROJECT_ROOT / "chroma_db")
PDF_DIR = _configured_path("LAW_PDF_DIR", PROJECT_ROOT / "pdf")
INPUT_DIR = _configured_path("LAW_INPUT_DIR", PROJECT_ROOT / "input")
OUTPUT_DIR = _configured_path("LAW_OUTPUT_DIR", PROJECT_ROOT / "output")
