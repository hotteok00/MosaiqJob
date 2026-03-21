"""MosaiqJob 로깅 설정.

파이프라인 내부 로그는 logging 모듈(stderr)로,
사용자 대면 출력은 Rich console(app.py)로 분리한다.
"""

import logging
import sys

_configured = False


def setup_logging(level: str = "INFO") -> None:
    """파이프라인 로깅을 설정한다. 중복 호출 시 무시."""
    global _configured
    if _configured:
        return
    _configured = True

    log_level = getattr(logging, level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        "[%(levelname).1s] %(name)s: %(message)s"
    ))

    root = logging.getLogger("mosaiq")
    root.setLevel(log_level)
    root.addHandler(handler)
