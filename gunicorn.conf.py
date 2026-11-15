"""Use the same worker configuration when Gunicorn starts at the repo root."""
from pathlib import Path

_config=Path(__file__).resolve().parent/'smartpoultry'/'gunicorn.conf.py'
exec(compile(_config.read_text(encoding='utf-8'),str(_config),'exec'),globals())
