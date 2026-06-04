@echo off
REM Windows 构建脚本
REM 产出 dist\inp-tool.exe (单文件,无需 Python 环境)
REM
REM 用法(在 Anaconda Prompt 中):
REM   activate cfdchanger
REM   scripts\build.bat
REM
REM 或在 Git Bash / WSL:
REM   cmd /c scripts\build.bat

setlocal enabledelayedexpansion

REM 切到项目根(inp_tool/)
cd /d "%~dp0\..\inp_tool"

echo ==^> [1/4] 检查 PyInstaller
python -c "import PyInstaller; print('  PyInstaller', PyInstaller.__version__)"

echo ==^> [2/4] 清理上次构建
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
mkdir dist

echo ==^> [3/4] PyInstaller 构建
pyinstaller --clean --noconfirm inp_tool.spec

echo ==^> [4/4] 验证产物
if not exist "dist\inp-tool.exe" (
    echo X  dist\inp-tool.exe 不存在! 1>&2
    exit /b 1
)

echo   OK dist\inp-tool.exe
for %%A in ("dist\inp-tool.exe") do echo   size: %%~zA bytes

REM 烟雾测试
echo ==^> 烟雾测试: --version
dist\inp-tool.exe --version

echo ==^> 烟雾测试: --help
dist\inp-tool.exe --help

echo.
echo Build 完成!
echo   产物: %CD%\dist\inp-tool.exe
echo   用法: dist\inp-tool.exe sweep ^<template^> ^<config^>
