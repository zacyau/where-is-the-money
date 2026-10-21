import hashlib
from pathlib import Path
from fastapi.templating import Jinja2Templates

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_STATIC_DIR = Path(__file__).parent / "static"


def _asset_version() -> str:
    """基于 static 目录全部文件的 mtime+size 生成版本号。

    静态文件任何改动 -> 版本号变化 -> 模板里的 ?v= 变化 -> 浏览器强制拉新，
    彻底避免发布新代码后用户浏览器仍命中旧缓存（如 company.js 的下载逻辑）。
    """
    h = hashlib.md5()
    for f in sorted(_STATIC_DIR.rglob("*")):
        if f.is_file():
            st = f.stat()
            h.update(f"{f.name}:{st.st_mtime_ns}:{st.st_size};".encode())
    return h.hexdigest()[:10]


templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
templates.env.globals["asset_ver"] = _asset_version()
