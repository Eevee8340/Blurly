@echo off
REM ── Blurly Engine Build Script ──────────────────────────────────────────
REM Run from the project root.
REM Output: bin\BlurlyEngine.dll

set "VS_PATH=C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools"
call "%VS_PATH%\VC\Auxiliary\Build\vcvars64.bat"

echo.
echo Compiling BlurlyEngine.cpp (multi-instance) ...
cl.exe /LD /O2 /EHsc /D_USRDLL /D_WINDLL ^
    src\BlurlyEngine.cpp ^
    /link /OUT:bin\BlurlyEngine.dll ^
    d3d11.lib dxgi.lib d3dcompiler.lib user32.lib

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [OK] bin\BlurlyEngine.dll built successfully.
) else (
    echo.
    echo [FAIL] Compilation failed with error %ERRORLEVEL%
)
