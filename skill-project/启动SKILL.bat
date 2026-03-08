@echo off
chcp 65001 >nul
title 报听写机器人 SKILL
echo.
echo ══════════════════════════════════════════
echo   报听写机器人 SKILL - 启动
echo ══════════════════════════════════════════
echo.
echo [1] 激活 Anaconda 环境...
call "E:\Download\Anaconda\Scripts\activate.bat" dictation_skill
echo [2] 启动 SKILL 后端 (端口3801)...
cd /d "E:\智能整理\dictation-robot\skill-project"
echo.
echo   SKILL管理面板: http://localhost:3801
echo   听写网页端:     http://localhost:3800
echo   首次启动将自动弹出API密钥授权对话框
echo.
python backend/app.py
pause
