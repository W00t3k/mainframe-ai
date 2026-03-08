//ICKDSF   JOB (1),ICKDSF,CLASS=A,MSGCLASS=X                              
//* ***************************************************************** * 
//* * INITIALIZE KICKS0 3350 DASD VOLUME                              * 
//* ***************************************************************** * 
//*                                                                     
//ICKDSF EXEC PGM=ICKDSF,REGION=4096K                                   
//SYSPRINT DD  SYSOUT=*                                                 
//SYSIN    DD  *                                                        
  INIT UNITADDRESS(351) VERIFY(111111) -                                
               VOLID(KICKS0) OWNER(HERCULES) -                          
               VTOC(0,1,15)                                             
//                                                                      
