@echo off
chcp 65001 > nul
echo.
echo  ======================================
echo   标书CT扫描仪 - 启动中...
echo  ======================================
echo.
echo  ✅ 隐私保障：文件仅在内存处理，关闭窗口即清空，无任何留底
echo.

REM 检查 Python 是否安装
python --version > nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 安装依赖（首次运行自动安装）
echo 检查依赖包...
pip install -r requirements.txt -q

echo.
echo  正在启动，浏览器将自动打开...
echo  如未自动打开，请访问: http://localhost:8501
echo  关闭此窗口即退出程序，所有数据立即清空
echo.

streamlit run app.py --server.headless false --browser.gatherUsageStats false

pause
