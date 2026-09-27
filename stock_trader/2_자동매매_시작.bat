@echo off
chcp 65001 > nul
cd /d "%~dp0"
python --version > nul 2>&1 || (echo [오류] Python이 설치되어 있지 않습니다. & pause & exit /b 1)
if not exist config.ini (
  copy config.example.ini config.ini > nul
  echo config.ini 를 만들었습니다. 메모장에서 appkey / secretkey 를 입력하고 저장한 뒤 다시 실행하세요.
  notepad config.ini
  pause
  exit /b 0
)
python -m pip install -q -r requirements.txt
python trader.py
echo.
pause
