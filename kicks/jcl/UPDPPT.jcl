//UPDPPT   JOB (1),UPDPPT,CLASS=A,MSGCLASS=X,MSGLEVEL=(1,1)
//*********************************************************************
//* UPDATE PPT (PROCESSING PROGRAM TABLE) FOR AI ASSISTANT            *
//* ADDS AIPGM PROGRAM AND AIMAPS MAPSET                              *
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
//SYSPUNCH DD DISP=SHR,DSN=KICKS.KICKSSYS.V1R5M0.SKIKLOAD(KIKPPTAI)
//SYSPRINT DD SYSOUT=*
//SYSIN    DD *
***********************************************************************
*        PPT ENTRIES FOR AI ASSISTANT                                 *
***********************************************************************
         PRINT NOGEN
KIKPPTAI CSECT
*
* AI ASSISTANT PROGRAM AND MAPSET
*
         KIKPPT TYPE=INITIAL,SUFFIX=AI
         KIKPPT PROGRAM=AIPGM,PGMLANG=COBOL
         KIKPPT MAPSET=AIMAPS
         KIKPPT TYPE=FINAL
*
         END
/*
//
