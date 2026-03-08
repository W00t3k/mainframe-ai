//ASMMAP   JOB (1),ASMMAP,CLASS=A,MSGCLASS=X,MSGLEVEL=(1,1)
//*********************************************************************
//* ASSEMBLE BMS MAP FOR AI ASSISTANT                                 *
//* INPUT:  KICKS.KICKS.V1R5M0.MAPSRC(AIMAPS)                        *
//* OUTPUT: KICKS.KICKS.V1R5M0.SKIKLOAD(AIMAPS)                      *
//*********************************************************************
//JOBLIB   DD DISP=SHR,DSN=KICKS.KICKSSYS.V1R5M0.SKIKLOAD
//*
//* STEP 1: ASSEMBLE MAP (PHYSICAL)
//*
//ASMMAP   EXEC KIKASM,MEM=AIMAPS
//SYSIN    DD DISP=SHR,DSN=KICKS.KICKS.V1R5M0.MAPSRC(AIMAPS)
//*
//* STEP 2: ASSEMBLE MAP (SYMBOLIC - DSECT)
//*
//ASMDSECT EXEC KIKASM,MEM=AIMAPS,PARM='DSECT'
//SYSIN    DD DISP=SHR,DSN=KICKS.KICKS.V1R5M0.MAPSRC(AIMAPS)
//
