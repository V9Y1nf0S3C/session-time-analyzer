@echo off
setlocal EnableDelayedExpansion
:: python3 script.py --req-file request.txt --grep-file patterns.txt --write-session-token token.txt

REM ----------------------------------------------------------------------------------------------------
REM --------------------- CUSTOMIZABLE PARAMETERS STARTS HERE ------------------------------------------
REM ----------------------------------------------------------------------------------------------------


:: Only useful when no request is provided manually. To avoid drag&drop every time during troubleshooting
set DEFAULT_FILE=request.txt


::Initial sleep before sending first request. If you are sure your cookie is valid for 20min, then start with 20
set INIT_SLEEP=0

::Delay between the first request and second request.
set DELAY=1

::From second request on wards, increase delay for every request. If this value is 2, then
:: R1>>R2 is 1 Min
:: R2>>R3 is 1+2 Min
:: R3>>R4 is 1+2+2 Min
:: R4>>R5 is 1+2+2+2 Min
:: R5>>R6 is 1+2+2+2+2 Min
set INCREMENT_DELAY=0


::If you want to proxy the request to see if any issue or if you want to log
:: set PROXY=http://localhost:8089


::Script will not execute more that the below request count. It is to restrict the script.
::set MAX_REQUESTS=5


::Script will stop executing if the delay between 2 requests is more than this. Useful when you dont want to track if the session timeout if morethan lets say 2Hrs.
:: set MAX_DELAY=3


:: If you want to store the reponse
:: set LOG_FILE=responses.log

:: Restrict the grep strings only to the body and ignore headers
:: set LOOK_ONLY_BODY=--look-only-body


:: Restrict the comparision to case sensitive search
:: set CASE_SENSITIVE=--case-sensitive-grep

:: If you want to store the portion of output in a file, here is the file name
set WRITE_TOKEN=token.txt


REM ----------------------------------------------------------------------------------------------------
REM --------------------- CUSTOMIZABLE PARAMETERS STOP HERE --------------------------------------------
REM ----------------------------------------------------------------------------------------------------



:: python script to launch
set PYTHON_SCRIPT=session-time-analyzer.py

:: Pattern file to grep the strings
set GREP_FILE=patterns.txt



if "%~1"=="" (
    call :RunAnalyzer "%DEFAULT_FILE%"
    goto :ExitScript
)

if "%~2"=="" (
    call :RunAnalyzer "%~1"
    goto :ExitScript
)

for %%i in (%*) do (
    set "tempFile=%temp%\analyzer_%%~ni.bat"
    (
        echo @echo off
        echo setlocal EnableDelayedExpansion
        echo set "CMD=python %PYTHON_SCRIPT% --req-file "%%~i""
        echo if "%INIT_SLEEP%" NEQ "" set "CMD=%%CMD%% --init-sleep %INIT_SLEEP%"
        echo if "%DELAY%" NEQ "" set "CMD=%%CMD%% --delay %DELAY%"
        echo if "%WRITE_TOKEN%" NEQ "" set "CMD=%%CMD%% --write-session-token %WRITE_TOKEN%"
        echo if "%INCREMENT_DELAY%" NEQ "" set "CMD=%%CMD%% --increment-delay %INCREMENT_DELAY%"
        echo if "%PROXY%" NEQ "" set "CMD=%%CMD%% --proxy %PROXY%"
        echo if "%MAX_REQUESTS%" NEQ "" set "CMD=%%CMD%% --max-requests %MAX_REQUESTS%"
        echo if "%MAX_DELAY%" NEQ "" set "CMD=%%CMD%% --max-delay %MAX_DELAY%"
        echo if "%LOG_FILE%" NEQ "" set "CMD=%%CMD%% --log-resp %LOG_FILE%"
        echo if "%LOOK_ONLY_BODY%" NEQ "" set "CMD=%%CMD%% %LOOK_ONLY_BODY%"
        echo if "%CASE_SENSITIVE%" NEQ "" set "CMD=%%CMD%% %CASE_SENSITIVE%"
        echo if "%GREP_FILE%" NEQ "" set "CMD=%%CMD%% --grep-file %GREP_FILE%"
        echo title Session Timeout Analyzer - %%~nxi
        echo echo Running analysis for %%~i
        echo echo Command: %%CMD%%
        echo %%CMD%%
        echo echo.
        echo echo Going to exit in 3 actions...
        echo pause ^>nul
        echo echo Going to exit in 2 actions...
        echo pause ^>nul
        echo echo Going to exit in 1 actions...
        echo pause ^>nul
    ) > "!tempFile!"
    start cmd /k ""!tempFile!""
)
goto :ExitScript

:RunAnalyzer
set "CMD=python %PYTHON_SCRIPT% --req-file "%~1""
if defined INIT_SLEEP set "CMD=!CMD! --init-sleep !INIT_SLEEP!"
if defined DELAY set "CMD=!CMD! --delay !DELAY!"
if defined WRITE_TOKEN set "CMD=!CMD! --write-session-token !WRITE_TOKEN!"
if defined INCREMENT_DELAY set "CMD=!CMD! --increment-delay !INCREMENT_DELAY!"
if defined PROXY set "CMD=!CMD! --proxy !PROXY!"
if defined MAX_REQUESTS set "CMD=!CMD! --max-requests !MAX_REQUESTS!"
if defined MAX_DELAY set "CMD=!CMD! --max-delay !MAX_DELAY!"
if defined LOG_FILE set "CMD=!CMD! --log-resp !LOG_FILE!"
if defined LOOK_ONLY_BODY set "CMD=!CMD! !LOOK_ONLY_BODY!"
if defined CASE_SENSITIVE set "CMD=!CMD! !CASE_SENSITIVE!"
if defined GREP_FILE set "CMD=!CMD! --grep-file !GREP_FILE!"

title Session Timeout Analyzer - %~nx1
echo Running analysis for %~1
echo Command: !CMD!
!CMD!

echo.
echo Going to exit in 3 actions...
pause >nul
echo Going to exit in 2 actions...
pause >nul
echo Going to exit in 1 actions...
pause >nul
exit /b 0

:ExitScript
exit /b 0