@echo off
chcp 65001 > nul
cd /d "%~dp0"
echo === 나노바나나 컷 이미지 자동 생성 ===
python --version > nul 2>&1 || (echo [오류] Python이 설치되어 있지 않습니다. https://www.python.org 에서 설치하세요. & pause & exit /b 1)
python -m pip install -q -r requirements.txt
python generate_images.py %*
echo.
pause
