//RECV370  JOB (1),'UNPACK XMIT',CLASS=A,MSGCLASS=X            
//*------------------------------------------------------------
//* UPLOAD KICKS XMIT FILE FROM CARD READER
//* HERCULES CMD: devinit 01c /path/kicks-tso-v1r5m0.xmi ebcdic
//*------------------------------------------------------------
//RECV1   EXEC RECV370                                         
//XMITIN   DD  UNIT=01C,DCB=BLKSIZE=80           
//SYSUT2   DD  DSN=KICKS.V1R5M0.INSTALL,         
//             VOL=SER=KICKS0,UNIT=3350,                       
//             SPACE=(TRK,(600,,8),RLSE),                      
//             DISP=(,CATLG)                                   
//                                                              
