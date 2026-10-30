@echo off
setlocal
echo ========================================================
echo   Smart Civic Guardian - Push to GitHub
echo ========================================================
echo Remote: https://github.com/Rakshak1512/smart-civic-guardian.git
echo Branch: main
echo.

set "GIT_CMD=git"
if exist "C:\Program Files\Git\cmd\git.exe" (
    set "GIT_CMD=C:\Program Files\Git\cmd\git.exe"
) else if exist "%USERPROFILE%\.gemini\antigravity\brain\08ea8161-1cfe-4bd7-9c13-6c3749b0d02d\scratch\mingit\cmd\git.exe" (
    set "GIT_CMD=%USERPROFILE%\.gemini\antigravity\brain\08ea8161-1cfe-4bd7-9c13-6c3749b0d02d\scratch\mingit\cmd\git.exe"
)

set /p GITHUB_TOKEN="Enter your GitHub Personal Access Token (PAT): "
if "%GITHUB_TOKEN%"=="" (
    echo [ERROR] No token entered.
    pause
    exit /b 1
)

echo.
echo Pushing to GitHub main...
"%GIT_CMD%" push https://%GITHUB_TOKEN%@github.com/Rakshak1512/smart-civic-guardian.git main
echo.
echo [DONE]
pause
