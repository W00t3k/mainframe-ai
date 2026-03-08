//COBCOMP  JOB (1),COBCOMP,CLASS=A,MSGCLASS=X,MSGLEVEL=(1,1)
//*********************************************************************
//* COMPILE COBOL PROGRAM FOR AI ASSISTANT                            *
//* INPUT:  KICKS.KICKS.V1R5M0.COB(AIPGM)                            *
//* OUTPUT: KICKS.KICKS.V1R5M0.SKIKLOAD(AIPGM)                       *
//*********************************************************************
//JOBLIB   DD DISP=SHR,DSN=KICKS.KICKSSYS.V1R5M0.SKIKLOAD
//*
//* COMPILE COBOL PROGRAM WITH KICKS PREPROCESSOR
//*
//COMPILE  EXEC KIKCOB,MEM=AIPGM
//SYSIN    DD DISP=SHR,DSN=KICKS.KICKS.V1R5M0.COB(AIPGM)
//
