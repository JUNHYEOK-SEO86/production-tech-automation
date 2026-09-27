#!/usr/bin/env bash
# Mac/Linux 실행 스크립트
cd "$(dirname "$0")"
python3 -m pip install -q -r requirements.txt
python3 generate_images.py "$@"
