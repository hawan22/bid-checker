@echo off
chcp 65001 > nul
echo.
echo  ============================================
echo   标书CT扫描仪 - 局域网共享模式启动中...
echo  ============================================
echo.

REM 获取本机IP
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /R "IPv4.*10\.\|IPv4.*192\.\|IPv4.*172\."') do (
    set LOCAL_IP=%%a
    goto :found_ip
)
:found_ip
set LOCAL_IP=%LOCAL_IP: =%

REM 检查 Python 是否安装
python --version > nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

REM 安装依赖（首次运行自动安装）
echo 检查依赖包...
pip install -r requirements.txt -q

echo.
echo  ================================================
echo   访问地址（同一WiFi下的设备均可打开）：
echo.
echo   本机：      http://localhost:8501
echo   手机/其他电脑：http://%LOCAL_IP%:8501
echo.
echo   ✅ 隐私保障：
echo   - 所有文件仅在内存中处理，不写入磁盘
echo   - 关闭此窗口后所有数据立即消失
echo   - 无账号、无日志、无任何留底
echo   - 仅限公司内网使用，不暴露至公网
echo  ================================================
echo.
echo  关闭此黑色窗口即退出，所有数据清空
echo.

streamlit run app.py ^
  --server.address 0.0.0.0 ^
  --server.port 8501 ^
  --server.headless true ^
  --browser.gatherUsageStats false ^
  --server.enableCORS false ^
  --server.enableXsrfProtection true

pause
