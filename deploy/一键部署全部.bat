@echo off
chcp 65001 >nul
title 报听写机器人 - 一键部署
echo.
echo ═══════════════════════════════════════════════════
echo   报听写机器人 - 一键部署全部
echo ═══════════════════════════════════════════════════
echo.
echo  [1] 启动网页端服务
echo  [2] 部署微信小程序
echo  [3] 全部部署
echo.
set /p choice="请选择 (1/2/3): "

if "%choice%"=="1" goto web
if "%choice%"=="2" goto mini
if "%choice%"=="3" goto all
goto end

:web
echo.
echo 正在启动网页端服务...
start "" "E:\智能整理\dictation-robot\启动报听写机器人.bat"
echo 网页端: http://localhost:3800
goto end

:mini
echo.
echo 正在部署微信小程序...
powershell -ExecutionPolicy Bypass -File "E:\智能整理\dictation-robot\deploy\deploy_miniprogram.ps1"
goto end

:all
echo.
echo 正在全部部署...
start "" "E:\智能整理\dictation-robot\启动报听写机器人.bat"
echo.
echo 网页端已启动: http://localhost:3800
echo.
powershell -ExecutionPolicy Bypass -File "E:\智能整理\dictation-robot\deploy\deploy_miniprogram.ps1"
goto end

:end
echo.
pause
