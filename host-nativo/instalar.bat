@echo off
echo Registrando el host nativo para Chrome...

:: Esto obtiene la ruta completa y exacta de tu host_manifest.json
set "MANIFEST_PATH=%~dp0host_manifest.json"

:: Esto agrega la clave al Registro de Windows (solo para tu usuario actual)
REG ADD "HKCU\Software\Google\Chrome\NativeMessagingHosts\com.leo.detector_duplicados" /ve /t REG_SZ /d "%MANIFEST_PATH%" /f

echo.
echo ¡Registro completado con exito! Chrome ya sabe donde encontrar tu programa.
pause