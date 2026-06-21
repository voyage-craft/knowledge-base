@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
echo ============================================
echo   AI Knowledge Base - Stopping...
echo ============================================
echo.

set "FOUND=0"

:: 1) Kill child windows by title (/T = kill process tree)
for /f "tokens=2" %%a in ('tasklist /fi "WINDOWTITLE eq KB-Backend*" /fo list 2^>nul ^| findstr "PID:"') do (
    echo   Killing KB-Backend ^(PID %%a^) and children...
    taskkill /PID %%a /F /T >nul 2>&1
    set "FOUND=1"
)
for /f "tokens=2" %%a in ('tasklist /fi "WINDOWTITLE eq KB-Frontend*" /fo list 2^>nul ^| findstr "PID:"') do (
    echo   Killing KB-Frontend ^(PID %%a^) and children...
    taskkill /PID %%a /F /T >nul 2>&1
    set "FOUND=1"
)

:: 2) Kill anything still listening on port 8000
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000.*LISTENING"') do (
    echo   Killing port 8000 process ^(PID %%a^) and children...
    taskkill /PID %%a /F /T >nul 2>&1
    set "FOUND=1"
)

:: 3) Kill anything still listening on port 3000
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":3000.*LISTENING"') do (
    echo   Killing port 3000 process ^(PID %%a^) and children...
    taskkill /PID %%a /F /T >nul 2>&1
    set "FOUND=1"
)

:: 4) Catch orphan child processes (workers spawned by uvicorn/next)
::    Check for python/node processes whose parent PID was one of the killed PIDs
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000.*LISTENING"') do (
    echo   Port 8000 still held, force killing PID %%a...
    taskkill /PID %%a /F /T >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":3000.*LISTENING"') do (
    echo   Port 3000 still held, force killing PID %%a...
    taskkill /PID %%a /F /T >nul 2>&1
)

echo.
if "!FOUND!"=="1" (
    echo All servers stopped. Ports 3000 and 8000 released.
) else (
    echo No running servers found. Ports are clean.
)
timeout /t 2 >nul
