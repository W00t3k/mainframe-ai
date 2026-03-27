//UPDVTAM  JOB (1),'UPD VTAMLST',CLASS=A,MSGCLASS=A,
//         MSGLEVEL=(1,1),USER=HERC01,PASSWORD=CUL8TR
//*
//* Step 1: Update L3274 - remove LOGAPPL=NETSOL
//*
//STEP1   EXEC PGM=IEBGENER
//SYSPRINT DD SYSOUT=*
//SYSIN    DD DUMMY
//SYSUT2   DD DSN=SYS1.VTAMLST(L3274),DISP=SHR
//SYSUT1   DD *
L3274    LBUILD SUBAREA=2
CUU0C0   LOCAL TERM=3277,CUADDR=0C0,ISTATUS=ACTIVE,                    +
               LOGTAB=ETHLOGVM,                                        +
               FEATUR2=(MODEL2,PFK)
CUU0C1   LOCAL TERM=3277,CUADDR=0C1,ISTATUS=ACTIVE,                    +
               LOGTAB=ETHLOGVM,                                        +
               FEATUR2=(MODEL2,PFK)
CUU0C2   LOCAL TERM=3277,CUADDR=0C2,ISTATUS=ACTIVE,                    +
               LOGTAB=ETHLOGVM,                                        +
               FEATUR2=(MODEL2,PFK)
CUU0C3   LOCAL TERM=3277,CUADDR=0C3,ISTATUS=ACTIVE,                    +
               LOGTAB=ETHLOGVM,                                        +
               FEATUR2=(MODEL2,PFK)
CUU0C4   LOCAL TERM=3277,CUADDR=0C4,ISTATUS=ACTIVE,                    +
               LOGTAB=ETHLOGVM,                                        +
               FEATUR2=(MODEL2,PFK)
CUU0C5   LOCAL TERM=3277,CUADDR=0C5,ISTATUS=ACTIVE,                    +
               LOGTAB=ETHLOGVM,                                        +
               FEATUR2=(MODEL2,PFK)
CUU0C6   LOCAL TERM=3277,CUADDR=0C6,ISTATUS=ACTIVE,                    +
               LOGTAB=ETHLOGVM,                                        +
               FEATUR2=(MODEL2,PFK)
CUU0C7   LOCAL TERM=3286,CUADDR=0C7,ISTATUS=ACTIVE
/*
//*
//* Step 2: Update ATCCON01 - remove ASNASOL from startup
//*
//STEP2   EXEC PGM=IEBGENER
//SYSPRINT DD SYSOUT=*
//SYSIN    DD DUMMY
//SYSUT2   DD DSN=SYS1.VTAMLST(ATCCON01),DISP=SHR
//SYSUT1   DD *
***********************************************************************
*  STARTLIST   T K 5                                                  *
***********************************************************************
ATSO,                              /* TSO application major node     */X
ASTF,                              /* Skybird Test Facility          */X
ARPF,                              /* RPF hardcopy monitor           */X
AICOM,                             /* Intercom application major node*/X
AJRP,                              /* JRP (JES2 remote print)        */X
L3274,                             /* local non-SNA major node       */X
L3791,                             /* local SNA major node           */X
S3705,                             /* switched SNA major node        */X
N07,                               /* local  3705 NCP subarea  7     */X
N08,                               /* remote 3705 NCP subarea  8     */X
N10,                               /* local  3705 NCP subarea 10     */X
N11,                               /* remote 3705 NCP subarea 11     */X
N12,                               /* local  3705 NCP subarea 12     */X
N13,                               /* remote 3705 NCP subarea 13     */X
N14,                               /* local  3705 NCP subarea 14     */X
N15                                /* remote 3705 NCP subarea 15     */
/*
//*
//* Step 3: Update ATCSTR00 - change NETSOL=YES to NETSOL=NO
//*
//STEP3   EXEC PGM=IEBGENER
//SYSPRINT DD SYSOUT=*
//SYSIN    DD DUMMY
//SYSUT2   DD DSN=SYS1.VTAMLST(ATCSTR00),DISP=SHR
//SYSUT1   DD *
CONFIG=01,                        /* CONFIG LIST SUFFIX              */+
SSCPID=01,                        /* THIS VTAMS ID IN NETWORK        */+
NETSOL=NO,                        /* NETWORK SOLICITOR OPTION        */+
USSTAB=ISTNSC00,                  /* USS TABLE                       */+
MAXSUBA=31,                       /* MAXIMUM SUBAREAS IN NETWORK     */+
NOPROMPT,                         /* OPERATOR PROMPT OPTION          */+
SUPP=NOSUP,                       /* MESSAGE SUPPRESSION OPTION      */+
COLD,                             /* RESTART OPTION   - COLD/WARM    */+
APBUF=(129,,116),                 /* ACE STORAGE POOL                */+
CRPLBUF=(1024,,768),              /* RPL COPY POOL                   */+
IOBUF=(50,4016,40,F),             /* FIXED IO                        */+
LFBUF=(104,,104,F),               /* LARGE FIXED BUFFER POOL         */+
LPBUF=(064,,64,F),                /* LARGE PAGEBLE BUFFER POOL       */+
NPBUF=(192,,176,F),               /* NON WS FMCB                     */+
PPBUF=(90,4016,80,F),             /* PAGEBLE IO                      */+
SFBUF=(163,,163,F),               /* SMALL FIXED BUFFER POOL         */+
SPBUF=(064,,64,F),                /* SMALL PGBL BUFFER POOL          */+
UECBUF=(34,,30,F),                /* USER EXIT CB                    */+
WPBUF=(78,,78,F)                  /* MESSAGE CONTROL BUFFER POOL     */
/*
//
