@echo off
chcp 65001 > nul
cd /d "%~dp0"
type nul > STOP
echo STOP 파일을 만들었습니다. 자동매매 프로그램이 보유 종목을 전량 매도하고 종료합니다.
echo 다음에 다시 실행하려면 이 폴더의 STOP 파일을 삭제하세요.
pause
