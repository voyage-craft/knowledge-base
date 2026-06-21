@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title AI Knowledge Base
echo ============================================
echo   AI Knowledge Base - Starting...
echo ============================================

:: ========== Pre-launch cleanup ==========
echo.
echo [Cleanup] Checking for existing processes on ports 3000/8000...
call :cleanup_ports

:: ========== Start backend ==========
echo.
echo [1/2] Starting backend ^(port 8000^)...
start "KB-Backend" cmd /k "title KB-Backend && cd /d "%~dp0backend" && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

:: Give backend a moment to bind its port
timeout /t 3 /nobreak >nul

:: ========== Start frontend ==========
echo [2/2] Starting frontend ^(port 3000^)...
start "KB-Frontend" cmd /k "title KB-Frontend && cd /d "%~dp0frontend" && npx next dev --port 3000"

:: ========== Status ==========
echo.
echo ============================================
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:3000
echo ============================================
echo.
echo Press any key to STOP all servers and clean up...
pause >nul

:: ========== Post-exit cleanup ==========
echo.
echo [Cleanup] Stopping all servers...
call :cleanup_ports
echo.
echo All servers stopped. Ports released.
timeout /t 2 >nul
goto :eof

:: ==========================================
:: Subroutine: Kill by window title + port
:: ==========================================
:cleanup_ports
:: 1) Kill child windows by title (/T = kill entire process tree)
for /f "tokens=2" %%a in ('tasklist /fi "WINDOWTITLE eq KB-Backend*" /fo list 2^>nul ^| findstr "PID:"') do (
    echo   Killing KB-Backend ^(PID %%a^) and children...
    taskkill /PID %%a /F /T >nul 2>&1
)
for /f "tokens=2" %%a in ('tasklist /fi "WINDOWTITLE eq KB-Frontend*" /fo list 2^>nul ^| findstr "PID:"') do (
    echo   Killing KB-Frontend ^(PID %%a^) and children...
    taskkill /PID %%a /F /T >nul 2>&1
)

:: 2) Kill anything still listening on port 8000
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000.*LISTENING"') do (
    echo   Killing port 8000 process ^(PID %%a^) and children...
    taskkill /PID %%a /F /T >nul 2>&1
)

:: 3) Kill anything still listening on port 3000
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":3000.*LISTENING"') do (
    echo   Killing port 3000 process ^(PID %%a^) and children...
    taskkill /PID %%a /F /T >nul 2>&1
)

:: 4) Second pass - catch orphan workers that re-bound the port
timeout /t 1 /nobreak >nul
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000.*LISTENING"') do (
    echo   Force killing residual port 8000 ^(PID %%a^)...
    taskkill /PID %%a /F /T >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":3000.*LISTENING"') do (
    echo   Force killing residual port 3000 ^(PID %%a^)...
    taskkill /PID %%a /F /T >nul 2>&1
)
goto :eof
