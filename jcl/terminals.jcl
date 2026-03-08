//TERMINAL JOB (1),'ADD TERMINALS',CLASS=A,MSGCLASS=X,MSGLEVEL=(1,1),
//             NOTIFY=IBMUSER
//*
//* Add 32 extra VTAM 3270 terminals to TK5 for multi-user access.
//*
//* Source: DC30_Workshop/jcl/terminals.jcl (adapted for TK5)
//*
//* After this job:
//*   - 32 new terminals at CUU addresses 400-41F are defined
//*   - Activate with: /V NET,ACT,ID=IBMAITER
//*   - Supports up to 32 concurrent TN3270 sessions
//*
//* NOTE: Also increase max users in SYS1.PARMLIB(IKJTSO00)
//*       USERS(50) to allow more concurrent TSO sessions.
//*
//*==================================================================
//*
//* STEP 1: Add VTAM terminal definitions to SYS1.VTAMLST
//*
//STORE   EXEC PGM=IEBUPDTE,REGION=1024K,PARM=NEW
//SYSPRINT DD  SYSOUT=*
//SYSUT2   DD  DSN=SYS1.VTAMLST,DISP=SHR
//SYSIN    DD  *
./ ADD NAME=ATCCON00,LIST=ALL
APPLTSO,                                             TSO APPLS         X
IBMAITER                                             LOCAL 3270S
./ ADD NAME=IBMAITER,LIST=ALL
LCL400   LBUILD SUBAREA=2
CUU400   LOCAL TERM=3277,CUADDR=400,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU401   LOCAL TERM=3277,CUADDR=401,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU402   LOCAL TERM=3277,CUADDR=402,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU403   LOCAL TERM=3277,CUADDR=403,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU404   LOCAL TERM=3277,CUADDR=404,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU405   LOCAL TERM=3277,CUADDR=405,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU406   LOCAL TERM=3277,CUADDR=406,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU407   LOCAL TERM=3277,CUADDR=407,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU408   LOCAL TERM=3277,CUADDR=408,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU409   LOCAL TERM=3277,CUADDR=409,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU40A   LOCAL TERM=3277,CUADDR=40A,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU40B   LOCAL TERM=3277,CUADDR=40B,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU40C   LOCAL TERM=3277,CUADDR=40C,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU40D   LOCAL TERM=3277,CUADDR=40D,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU40E   LOCAL TERM=3277,CUADDR=40E,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU40F   LOCAL TERM=3277,CUADDR=40F,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU410   LOCAL TERM=3277,CUADDR=410,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU411   LOCAL TERM=3277,CUADDR=411,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU412   LOCAL TERM=3277,CUADDR=412,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU413   LOCAL TERM=3277,CUADDR=413,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU414   LOCAL TERM=3277,CUADDR=414,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU415   LOCAL TERM=3277,CUADDR=415,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU416   LOCAL TERM=3277,CUADDR=416,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU417   LOCAL TERM=3277,CUADDR=417,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU418   LOCAL TERM=3277,CUADDR=418,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU419   LOCAL TERM=3277,CUADDR=419,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU41A   LOCAL TERM=3277,CUADDR=41A,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU41B   LOCAL TERM=3277,CUADDR=41B,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU41C   LOCAL TERM=3277,CUADDR=41C,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU41D   LOCAL TERM=3277,CUADDR=41D,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU41E   LOCAL TERM=3277,CUADDR=41E,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
CUU41F   LOCAL TERM=3277,CUADDR=41F,ISTATUS=ACTIVE,                    +
               LOGTAB=LOGTAB01,LOGAPPL=NETSOL,                         +
               FEATUR2=(MODEL2,PFK)
/*
//*
//* STEP 2: Increase max TSO users in IKJTSO00
//*
//TSOUSERS EXEC PGM=IEBUPDTE,PARM=NEW
//SYSPRINT DD  SYSOUT=*
//SYSUT2   DD  DSN=SYS1.PARMLIB,DISP=SHR
//SYSIN    DD  *
./ CHANGE NAME=IKJTSO00
USERS(50)
./ ENDUP
/*
