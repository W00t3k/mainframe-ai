//DEFCAT   JOB (1),DEFCAT,CLASS=A,MSGCLASS=X
//* *****************************************************************
//* * DEFINE USER CATALOG AND ALIAS FOR KICKS                       *
//* *****************************************************************
//IDCAMS01 EXEC PGM=IDCAMS,REGION=4096K
//SYSPRINT DD SYSOUT=*
//KICKS0   DD UNIT=SYSALLDA,DISP=OLD,VOL=SER=KICKS0
//SYSIN    DD *
  DEFINE USERCATALOG ( -
      NAME (UCKICKS0) -
      VOLUME (KICKS0) -
      TRACKS (7500 0) -
      FOR (9999) ) -
      DATA (TRACK (15 5) ) -
      INDEX (TRACKS (15) ) -
      CATALOG (SYS1.VMASTCAT/SYSPROG)

  DEFINE ALIAS ( -
      NAME (KICKS) -
      RELATE (UCKICKS0) ) -
      CATALOG (SYS1.VMASTCAT/SYSPROG)
//
