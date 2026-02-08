//RECV370 JOB (1),'UNPACK XMIT',CLASS=A,MSGCLASS=X
//JOBLIB   DD DISP=SHR,DSN=SYSC.LINKLIB
//*------------------------------------------------------------
//RECV1   EXEC RECV370
//XMITIN   DD UNIT=01C,DCB=BLKSIZE=80
//SYSUT2   DD DSN=KICKS.V1R5M0.INSTALL,
//            UNIT=SYSALLDA,
//            SPACE=(TRK,(600,,8),RLSE),
//            DISP=(,CATLG)
//
