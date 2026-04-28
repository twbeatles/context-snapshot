import locale
from typing import Optional

APP_NAME = "ctxsnap"

DEFAULT_TAGS_KO = ["업무", "개인", "부동산", "정산"]
DEFAULT_TAGS_EN = ["Work", "Personal", "Real Estate", "Settlement"]

# Backward-compatible constant for existing code paths. New settings should call
# default_tags_for_language() so first-run defaults follow the active language.
DEFAULT_TAGS = DEFAULT_TAGS_KO


def default_tags_for_language(lang_code: Optional[str] = None) -> list[str]:
    lang = (lang_code or "auto").lower()
    if lang == "auto":
        try:
            sys_lang = locale.getlocale()[0]
            lang = "ko" if sys_lang and sys_lang.lower().startswith("ko") else "en"
        except Exception:
            lang = "en"
    return list(DEFAULT_TAGS_KO if lang.startswith("ko") else DEFAULT_TAGS_EN)

DEFAULT_PROCESS_KEYWORDS = [
    "code",
    "pycharm",
    "idea",
    "chrome",
    "msedge",
    "firefox",
    "wt",
    "terminal",
    "powershell",
    "cmd",
    "python",
    "node",
    "docker",
    "postman",
    "slack",
    "notion",
]
