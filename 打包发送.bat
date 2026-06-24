@echo off
chcp 65001 > nul
echo.
echo  正在打包标书CT扫描仪便携版...
echo.

cd /d "%~dp0"

REM 目标 ZIP 文件名
set ZIP_NAME=标书CT扫描仪_portable_%date:~0,4%%date:~5,2%%date:~8,2%.zip

REM 检查 PowerShell
powershell -command "exit 0" > nul 2>&1
if errorlevel 1 (
    echo [错误] 需要 PowerShell 才能打包
    pause
    exit /b 1
)

REM 要打包的文件列表（排除 __pycache__ 和临时文件）
echo 正在压缩文件...

powershell -command ^
  "$src = '%~dp0'; ^
   $dst = Join-Path $src '%ZIP_NAME%'; ^
   if (Test-Path $dst) { Remove-Item $dst }; ^
   $exclude = @('__pycache__', '*.pyc', '.git', '*.zip', 'logs', 'browser_profile'); ^
   $files = Get-ChildItem -Path $src -Recurse | Where-Object { ^
     $rel = $_.FullName.Substring($src.Length); ^
     $skip = $false; ^
     foreach ($ex in $exclude) { if ($rel -like ('*\' + $ex + '*') -or $rel -like $ex) { $skip = $true; break } }; ^
     -not $skip -and -not $_.PSIsContainer ^
   }; ^
   Compress-Archive -Path $files.FullName -DestinationPath $dst -Force; ^
   Write-Host ('打包完成: ' + $dst)"

echo.
echo  ============================================
echo   打包完成！
echo.
echo   文件：%ZIP_NAME%
echo   位置：%~dp0
echo.
echo   发送给对方后，操作步骤：
echo   1. 解压到任意文件夹
echo   2. 双击「一键安装并启动.bat」（首次，约5分钟）
echo   3. 以后直接双击「run.bat」
echo  ============================================
echo.

REM 打开所在文件夹
explorer "%~dp0"
pause
