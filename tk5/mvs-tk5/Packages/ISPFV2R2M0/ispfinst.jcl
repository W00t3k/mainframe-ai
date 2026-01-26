//Z531415I JOB  01,ROBPRINS,CLASS=A,MSGCLASS=X,NOTIFY=&SYSUID,       
//         REGION=2048K                                              
//*                                                                  
//* CHANGE THE JOB CARD 'NAME' AND 'ACCT' TO SUIT YOUR INSTALLATION. 
//*                                                                  
//*                                                                  
//* CHANGE THE 'VVVVVV' AND 'UUUU' AS REQUIRED.                      
//*                                                                  
//LOAD     PROC HIL=ISP,DSN=LLIB,LABEL=1,                            
//         VOL=MOD001,UNIT=3390,CYL=2,MEM=20                         
//STEP1    EXEC PGM=IEBCOPY                                          
//SYSPRINT DD   SYSOUT=*                                             
//SYSUT1   DD   DSN=ISP.V2R2M0.&DSN..UNLOAD,DISP=(OLD,KEEP),         
//         VOL=(PRIVATE,RETAIN,SER=ISP220),UNIT=TAPE,                
//         LABEL=(&LABEL,SL,,IN)                                     
//SYSUT2   DD   DSN=&HIL..V2R2M0.&DSN,DISP=(,CATLG),                 
//         VOL=SER=&VOL,UNIT=&UNIT,SPACE=(CYL,(&CYL,0,&MEM),RLSE)    
//SYSIN    DD   DUMMY                                                
//         PEND                                                      
//DELETE   EXEC PGM=IEHPROGM                                         
//*                                                                  
//* CHANGE THE 'VVVVVV' AND 'UUUU' AS REQUIRED.                      
//*                                                                  
//SYSPRINT DD   SYSOUT=*                                             
//DASD     DD   VOL=SER=MOD001,UNIT=3390,DISP=SHR                    
//SYSIN    DD   *                                                    
 SCRATCH DSNAME=ISP.V2R2M0.INSTALL,VOL=3390=MOD001                   
 UNCATLG DSNAME=ISP.V2R2M0.INSTALL                                   
 SCRATCH DSNAME=ISP.V2R2M0.DOC,VOL=3390=MOD001                       
 UNCATLG DSNAME=ISP.V2R2M0.DOC                                       
 SCRATCH DSNAME=ISP.V2R2M0.CLIB,VOL=3390=MOD001                      
 UNCATLG DSNAME=ISP.V2R2M0.CLIB                                      
 SCRATCH DSNAME=ISP.V2R2M0.LLIB,VOL=3390=MOD001                      
 UNCATLG DSNAME=ISP.V2R2M0.LLIB                                      
 SCRATCH DSNAME=ISP.V2R2M0.MLIB,VOL=3390=MOD001                      
 UNCATLG DSNAME=ISP.V2R2M0.MLIB                                      
 SCRATCH DSNAME=ISP.V2R2M0.PLIB,VOL=3390=MOD001                      
 UNCATLG DSNAME=ISP.V2R2M0.PLIB                                      
 SCRATCH DSNAME=ISP.V2R2M0.SLIB,VOL=3390=MOD001                      
 UNCATLG DSNAME=ISP.V2R2M0.SLIB                                      
 SCRATCH DSNAME=ISP.V2R2M0.TLIB,VOL=3390=MOD001
 UNCATLG DSNAME=ISP.V2R2M0.TLIB                   
 SCRATCH DSNAME=ISP.V2R2M0.OPTDOC,VOL=3390=MOD001 
 UNCATLG DSNAME=ISP.V2R2M0.OPTDOC                 
 SCRATCH DSNAME=ISP.V2R2M0.OPTCLIB,VOL=3390=MOD001
 UNCATLG DSNAME=ISP.V2R2M0.OPTCLIB                
 SCRATCH DSNAME=ISP.V2R2M0.OPTLLIB,VOL=3390=MOD001
 UNCATLG DSNAME=ISP.V2R2M0.OPTLLIB                
 SCRATCH DSNAME=ISP.V2R2M0.OPTMLIB,VOL=3390=MOD001
 UNCATLG DSNAME=ISP.V2R2M0.OPTMLIB                
 SCRATCH DSNAME=ISP.V2R2M0.OPTPLIB,VOL=3390=MOD001
 UNCATLG DSNAME=ISP.V2R2M0.OPTPLIB                
 SCRATCH DSNAME=ISP.V2R2M0.OPTSLIB,VOL=3390=MOD001
 UNCATLG DSNAME=ISP.V2R2M0.OPTSLIB                
//INSTALL  EXEC LOAD,DSN=INSTALL,LABEL=1          
//DOC      EXEC LOAD,DSN=DOC,LABEL=2              
//CLIB     EXEC LOAD,DSN=CLIB,LABEL=3             
//LLIB     EXEC LOAD,DSN=LLIB,LABEL=4             
//MLIB     EXEC LOAD,DSN=MLIB,LABEL=5             
//PLIB     EXEC LOAD,DSN=PLIB,LABEL=6             
//SLIB     EXEC LOAD,DSN=SLIB,LABEL=7             
//TLIB     EXEC LOAD,DSN=TLIB,LABEL=8             
//OPTDOC   EXEC LOAD,DSN=OPTDOC,LABEL=9           
//OPTCLIB  EXEC LOAD,DSN=OPTCLIB,LABEL=10         
//OPTLLIB  EXEC LOAD,DSN=OPTLLIB,LABEL=11         
//OPTMLIB  EXEC LOAD,DSN=OPTMLIB,LABEL=12         
//OPTPLIB  EXEC LOAD,DSN=OPTPLIB,LABEL=13         
//OPTSLIB  EXEC LOAD,DSN=OPTSLIB,LABEL=14         
//                                                                      