//IBMAIUS  JOB (1),'AIOS USS',CLASS=A,MSGCLASS=A,
//         MSGLEVEL=(1,1),USER=HERC01,PASSWORD=CUL8TR
//*
//* AI/OS - Custom VTAM USS Logon Screen for TK5
//* Based on github.com/mainframed/usstable
//*
//ASM     EXEC PGM=IFOX00,REGION=1024K
//SYSLIB  DD DSN=SYS1.MACLIB,DISP=SHR
//        DD DSN=SYS1.AMACLIB,DISP=SHR
//        DD DSN=SYS2.MACLIB,DISP=SHR
//        DD DSN=SYS1.AMODGEN,DISP=SHR
//SYSUT1  DD UNIT=VIO,SPACE=(1700,(600,100))
//SYSUT2  DD UNIT=VIO,SPACE=(1700,(300,50))
//SYSUT3  DD UNIT=VIO,SPACE=(1700,(300,50))
//SYSPRINT DD SYSOUT=*
//SYSPUNCH DD DSN=&&OBJ,DISP=(NEW,PASS),UNIT=VIO,
//         SPACE=(TRK,(2,2)),
//         DCB=(BLKSIZE=80,LRECL=80,RECFM=F)
//SYSIN   DD *
*
*  AI/OS USS TABLE FOR TK5 MVS 3.8J
*
USSTAB   USSTAB TABLE=STDTRANS
*
TSO      USSCMD CMD=TSO,REP=LOGON,FORMAT=BAL
         USSPARM PARM=APPLID,DEFAULT=TSO
         USSPARM PARM=P1,REP=DATA
*
LOGON    USSCMD CMD=LOGON,REP=LOGON,FORMAT=BAL
         USSPARM PARM=APPLID,DEFAULT=TSO
         USSPARM PARM=P1,REP=DATA
*
LOGOFF   USSCMD CMD=LOGOFF,REP=LOGOFF,FORMAT=BAL
*
         USSMSG MSG=00,BUFFER=BUF00
         USSMSG MSG=01,TEXT='Invalid command syntax'
         USSMSG MSG=02,TEXT='Command unrecognized'
         USSMSG MSG=03,TEXT='Parameter extraneous'
         USSMSG MSG=05,TEXT='Key pressed is inactive'
         USSMSG MSG=06,TEXT='No such session exists'
         USSMSG MSG=08,TEXT='Command failed - storage'
         USSMSG MSG=10,TEXT=' '
         USSMSG MSG=11,TEXT='Session has ended'
         USSMSG MSG=12,TEXT='Required parameter missing'
         USSMSG MSG=14,TEXT='USS message not defined'
*
STDTRANS DC X'000102030440060708090A0B0C0D0E0F'
         DC X'101112131415161718191A1B1C1D1E1F'
         DC X'202122232425262728292A2B2C2D2E2F'
         DC X'303132333435363738393A3B3C3D3E3F'
         DC X'404142434445464748494A4B4C4D4E4F'
         DC X'505152535455565758595A5B5C5D5E5F'
         DC X'604062636465666768696A6B6C6D6E6F'
         DC X'707172737475767778797A7B7C7D7E7F'
         DC X'80C1C2C3C4C5C6C7C8C98A8B8C8D8E8F'
         DC X'90D1D2D3D4D5D6D7D8D99A9B9C9D9E9F'
         DC X'A0A1E2E3E4E5E6E7E8E9AAABACADAEAF'
         DC X'B0B1B2B3B4B5B6B7B8B9BABBBCBDBEBF'
         DC X'C0C1C2C3C4C5C6C7C8C9CACBCCCDCECF'
         DC X'D0D1D2D3D4D5D6D7D8D9DADBDCDDDEDF'
         DC X'E0E1E2E3E4E5E6E7E8E9EAEBECEDEEEF'
         DC X'F0F1F2F3F4F5F6F7F8F9FAFBFCFDFEFF'
END      USSEND
*
***********************************************************
* LOGON SCREEN (MSG 00) - AI/OS CUSTOM SCREEN
***********************************************************
BUF00    DS 0F
BUF00LEN DC AL2(BUF00E-BUF00B)        BUFFER LENGTH
BUF00B   EQU *
         DC X'F5C3'                    ERASE/WRITE WCC
         DC X'114040'                  SBA R1C1
         DC X'1DE8'                    SF PROT HI
         DC C'+--------------------------------------'
         DC C'--------------------------------------+'
         DC X'1DE8'
         DC C'|                                      '
         DC C'                                      |'
         DC X'1DE8'
         DC C'|   AI/OS - Artificial Intelligence Ope'
         DC C'rating System  v1.0                   |'
         DC X'1DE8'
         DC C'|                                      '
         DC C'                                      |'
         DC X'1D60'
         DC C'|   MVS 3.8j TK5 - Hercules Mainframe '
         DC C'Emulator                              |'
         DC X'1D60'
         DC C'|   Not your grandfathers z/OS. Well, a'
         DC C'ctually...                            |'
         DC X'1D60'
         DC C'|--------------------------------------'
         DC C'--------------------------------------|'
         DC X'1D60'
         DC C'|  KERNEL : MVS 3.8j TK5 (Hercules)   '
         DC C'   NODE: AIOS    ARCH: S/370 ESA      |'
         DC X'1D60'
         DC C'|  AI     : OLLAMA LOCAL LLM           '
         DC C'   PORT: 8080    SECURITY: RACF        |'
         DC X'1D60'
         DC C'|--------------------------------------'
         DC C'--------------------------------------|'
         DC X'1DE8'
         DC C'|  ** AUTHORIZED ACCESS ONLY **        '
         DC C'                                      |'
         DC X'1D60'
         DC C'|  Research and education platform.    '
         DC C'Sessions monitored.                   |'
         DC X'1D60'
         DC C'|  CAPS: TN3270 FTP JCL/JES RACF COBOL'
         DC C' AI-TUTOR                             |'
         DC X'1D60'
         DC C'|  LABS: BufOvfl APF-Privesc RACF-Hash '
         DC C'FTP-RCE                               |'
         DC X'1D60'
         DC C'|--------------------------------------'
         DC C'--------------------------------------|'
         DC X'1D60'
         DC C'|  CMD: TSO | CICS/KICKS | FTP:2121 | '
         DC C'USS-EDIT | web:8080                   |'
         DC X'1D60'
         DC C'|                                      '
         DC C'                                      |'
         DC X'1DE8'
         DC C'|  Logon ===> '
         DC X'1D40'                    SF UNPROT
         DC X'13'                      INSERT CURSOR
         DC C'                                         '
         DC C'                   '
         DC X'1DE8'
         DC C'|'
         DC X'1D60'
         DC C'|                                      '
         DC C'                                      |'
         DC X'1D60'
         DC C'|  github.com/W00t3k/mainframe-ai     '
         DC C'AI/OS on MVS 3.8j / TK5              |'
         DC X'1DE8'
         DC C'+--------------------------------------'
         DC C'--------------------------------------+'
BUF00E   EQU *
         END
/*
//*
//* STEP 2 - LINK INTO SYS1.VTAMLIB
//*
//LKED    EXEC PGM=IEWL,
//        PARM='XREF,LIST,LET,NCAL',
//        REGION=1024K,
//        COND=(8,LT,ASM)
//SYSPRINT DD SYSOUT=*
//SYSLIN  DD DSN=&&OBJ,DISP=(OLD,DELETE)
//SYSLMOD DD DSN=SYS1.VTAMLIB,DISP=SHR
//SYSUT1  DD UNIT=VIO,SPACE=(1024,(200,20))
//SYSIN   DD *
 NAME ISTNSC00(R)
/*
//