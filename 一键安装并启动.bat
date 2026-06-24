@echo off
chcp 65001 > nul
echo.
echo  ============================================
echo   标书CT扫描仪 v1.7 — 一键安装 ^& 启动
echo  ============================================
echo.

REM ── 检查 Python ──────────────────────────────────────────────
python --version > nul 2>&1
if errorlevel 1 (
    echo  [!] 未检测到 Python，正在帮你打开下载页...
    echo.
    echo  安装步骤：
    echo    1. 浏览器打开后点 "Download Python 3.x.x"
    echo    2. 安装时务必勾选 "Add Python to PATH"  ← 很重要！
    echo    3. 安装完成后，重新双击本文件即可
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo  检测到 %PY_VER% ✅
echo.

REM ── 安装依赖 ─────────────────────────────────────────────────
echo  正在安装依赖包（首次约需 3~8 分钟，请耐心等待）...
echo  （安装完成后会自动打开浏览器）
echo.
python -m pip install --upgrade pip -q
pip install -r requirements.txt -q

if errorlevel 1 (
    echo.
    echo  [错误] 安装失败，请检查网络后重试，或联系 Hattie
    pause
    exit /b 1
)

echo.
echo  ✅ 安装完成！正在启动...
echo  （浏览器会自动打开，地址是 http://localhost:8501）
echo.
echo  关闭此窗口即可退出程序
echo  ============================================
echo.
streamlit run app.py --server.headless false --browser.gatherUsageStats false --server.port 8501
pause
