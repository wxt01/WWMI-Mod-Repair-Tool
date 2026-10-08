@echo off
chcp 65001 >nul
echo ============================================
echo   WWMI MOD 修复助手 - 一键打包
echo ============================================
cd /d "%~dp0"
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo 未安装 PyInstaller，先安装...
    pip install pyinstaller
)
pyinstaller --noconfirm --clean "WWMI_MOD修复助手.spec"
echo.
echo 打包完成：dist\WWMI_MOD修复助手.exe
pause
