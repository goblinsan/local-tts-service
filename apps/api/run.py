from __future__ import annotations

from pathlib import Path

import uvicorn

from apps.api.logging_config import setup_logging


def main() -> None:
    root_dir = Path(__file__).resolve().parents[2]
    setup_logging(root_dir / "logs")
    uvicorn.run("apps.api.main:app", host="0.0.0.0", port=5000, log_config=None)


if __name__ == "__main__":
    main()
