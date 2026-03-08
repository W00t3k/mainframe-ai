//UPDPCT   JOB (1),UPDPCT,CLASS=A,MSGCLASS=X,MSGLEVEL=(1,1)
//*********************************************************************
//* UPDATE PCT (PROGRAM CONTROL TABLE) FOR AI ASSISTANT               *
//* ADDS AIMP TRANSACTION                                             *
//*********************************************************************
//JOBLIB   DD DISP=SHR,DSN=SYS1.LINKLIB
//         DD DISP=SHR,DSN=KICKS.KICKSSYS.V1R5M0.SKIKLOAD
//*
//ASM      EXEC PGM=IFOX00,REGION=4096K,
//             PARM='DECK,NOLIST,NOTERM,NOXREF'
//SYSLIB   DD DISP=SHR,DSN=KICKS.KICKSSYS.V1R5M0.MACLIB
//         DD DISP=SHR,DSN=SYS1.MACLIB
//SYSUT1   DD UNIT=VIO,SPACE=(CYL,(5,5))
//SYSUT2   DD UNIT=VIO,SPACE=(CYL,(5,5))
//SYSUT3   DD UNIT=VIO,SPACE=(CYL,(5,5))
//SYSPUNCH DD DISP=SHR,DSN=KICKS.KICKSSYS.V1R5M0.SKIKLOAD(KIKPCTAI)
//SYSPRINT DD SYSOUT=*
//SYSIN    DD *
***********************************************************************
*        PCT ENTRIES FOR AI ASSISTANT                                 *
***********************************************************************
         PRINT NOGEN
KIKPCTAI CSECT
*
* AI ASSISTANT TRANSACTION
*
         KIKPCT TYPE=INITIAL,SUFFIX=AI
         KIKPCT TRANSID=AIMP,PROGRAM=AIPGM,TWASIZE=100
         KIKPCT TYPE=FINAL
*
         END
/*
//
