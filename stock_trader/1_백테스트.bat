@echo off
chcp 65001 > nul
cd /d "%~dp0"
python --version > nul 2>&1 || (echo [오류] Python이 설치되어 있지 않습니다. & pause & exit /b 1)
python -m pip install -q -r requirements.txt
echo === k 값별 백테스트 (최근 데이터) ===
python backtest.py --sweep %*
echo.
pause
