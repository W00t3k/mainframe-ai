@ECHO OFF
REM **********************************************************************
REM ***                                                                ***
REM *** Script:  mvs.bat                                               ***
REM ***                                                                ***
REM *** Purpose: IPL OS/VS2-MVS 3.8j (tk5 unattended operations)       ***
REM ***                                                                ***
REM *** Updated: 2023/05/30                                            ***
REM ***                                                                ***
REM **********************************************************************
setlocal
REM *
REM * set environment
REM *
SET ARCH=32
IF DEFINED ProgramFiles(x86) SET ARCH=64
SET DAEMON=-d
SET EXPLICIT_LOG=log log\3033.log
IF NOT EXIST unattended\mode GOTO default
SET /P MODE=<unattended\mode
IF "x%MODE%" neq "xCONSOLE" GOTO default
SET DAEMON=
SET EXPLICIT_LOG=
:default
REM *
REM * source configuration variables
REM *
IF NOT EXIST local_conf\tk5.parm GOTO noparm
COPY /Y local_conf\tk5.parm .\parm.bat >NUL 2>&1
CALL parm.bat
ERASE /F /Q parm.bat >NUL 2>&1
:noparm
IF "x%REP101A%" equ "xspecific" IF "x%CMD101A%" equ "x%CMD101A%" SET CMD101A=02
REM *
REM * IPL OS/VS2-MVS 3.8j
REM *
ERASE /F /Q log\3033.log >NUL 2>&1
SET HERCULES_RC=scripts\ipl.rc
SET TK5CRLF=CRLF
IF "x%DAEMON%" equ "x" .\hercules\windows\%ARCH%\hercules %DAEMON% -f conf\tk5.cnf >log/3033.log
IF "x%DAEMON%" neq "x" START "" /B .\hercules\windows\utils\quiet .\hercules\windows\%ARCH%\hercules %DAEMON% -f conf\tk5.cnf
IF "x%DAEMON%" neq "x" CMD /C "TIMEOUT 5 >NUL 2>&1"
IF "x%DAEMON%" neq "x" START "" /B .\hercules\windows\utils\tail -f log\3033.log
