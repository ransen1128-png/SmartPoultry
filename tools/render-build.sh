#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
pip install -r requirements-render.txt
# Keep the desktop's exact inference version without pulling GUI-only OpenCV.
pip install --no-deps ultralytics==8.3.221
python tools/check_vision_runtime.py
python tools/prepare_vision_models.py
python smartpoultry/manage.py collectstatic --noinput
