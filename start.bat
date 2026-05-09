@echo off
echo Starting Game Design AI Assistant...

:: 启动 Python 后端 (在后台)
start /b python api/main.py

:: 等待后端启动
timeout /t 3

:: 启动 Electron 前端
npm run electron:dev
