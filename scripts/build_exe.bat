@echo off
setlocal
cd /d %~dp0\..

REM Create virtualenv if you want:
REM python -m venv .venv
REM call .venv\Scripts\activate

pip install -r requirements.txt

pyinstaller --noconfirm --clean ctxsnap_win.spec

echo.
echo Build complete. See dist\CtxSnap\CtxSnap.exe
pause
