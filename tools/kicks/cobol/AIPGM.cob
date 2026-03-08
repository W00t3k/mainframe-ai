       IDENTIFICATION DIVISION.
       PROGRAM-ID. AIPGM.
      *****************************************************************
      * AI MAINFRAME ASSISTANT - CICS TRANSACTION PROGRAM             *
      * FOR KICKS ON MVS 3.8J                                         *
      *                                                               *
      * TRANSACTION ID: AIMP                                          *
      *                                                               *
      * THIS PROGRAM:                                                 *
      * 1. DISPLAYS THE AI ASSISTANT BMS SCREEN                       *
      * 2. ACCEPTS USER QUESTION INPUT                                *
      * 3. WRITES QUESTION TO TRANSIENT DATA QUEUE                    *
      * 4. READS RESPONSE FROM RESPONSE QUEUE                         *
      * 5. DISPLAYS RESPONSE ON SCREEN                                *
      *                                                               *
      * NOTE: ACTUAL AI PROCESSING IS DONE BY EXTERNAL BRIDGE         *
      * THAT MONITORS THE QUEUES AND CALLS THE AI SERVICE             *
      *****************************************************************
       ENVIRONMENT DIVISION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
      *
      * COMMUNICATION AREA
      *
       01  WS-COMMAREA.
           05  WS-COMM-FLAG          PIC X(01).
               88  FIRST-TIME        VALUE SPACE.
               88  RETURN-ENTRY      VALUE 'R'.
      *
      * BMS MAP AREAS
      *
       01  AIMAP1I.
           05  FILLER                PIC X(12).
           05  DATEIL               PIC S9(4) COMP.
           05  DATEIF               PIC X(01).
           05  FILLER REDEFINES DATEIF.
               10  DATEIA           PIC X(01).
           05  DATEI                PIC X(8).
           05  QUESTIL              PIC S9(4) COMP.
           05  QUESTIF              PIC X(01).
           05  FILLER REDEFINES QUESTIF.
               10  QUESTIA          PIC X(01).
           05  QUESTI               PIC X(72).
           05  RESP01L              PIC S9(4) COMP.
           05  RESP01F              PIC X(01).
           05  FILLER REDEFINES RESP01F.
               10  RESP01A          PIC X(01).
           05  RESP01I              PIC X(76).
           05  RESP02L              PIC S9(4) COMP.
           05  RESP02F              PIC X(01).
           05  FILLER REDEFINES RESP02F.
               10  RESP02A          PIC X(01).
           05  RESP02I              PIC X(76).
           05  RESP03L              PIC S9(4) COMP.
           05  RESP03F              PIC X(01).
           05  FILLER REDEFINES RESP03F.
               10  RESP03A          PIC X(01).
           05  RESP03I              PIC X(76).
           05  RESP04L              PIC S9(4) COMP.
           05  RESP04F              PIC X(01).
           05  FILLER REDEFINES RESP04F.
               10  RESP04A          PIC X(01).
           05  RESP04I              PIC X(76).
           05  RESP05L              PIC S9(4) COMP.
           05  RESP05F              PIC X(01).
           05  FILLER REDEFINES RESP05F.
               10  RESP05A          PIC X(01).
           05  RESP05I              PIC X(76).
           05  RESP06L              PIC S9(4) COMP.
           05  RESP06F              PIC X(01).
           05  FILLER REDEFINES RESP06F.
               10  RESP06A          PIC X(01).
           05  RESP06I              PIC X(76).
           05  RESP07L              PIC S9(4) COMP.
           05  RESP07F              PIC X(01).
           05  FILLER REDEFINES RESP07F.
               10  RESP07A          PIC X(01).
           05  RESP07I              PIC X(76).
           05  RESP08L              PIC S9(4) COMP.
           05  RESP08F              PIC X(01).
           05  FILLER REDEFINES RESP08F.
               10  RESP08A          PIC X(01).
           05  RESP08I              PIC X(76).
           05  RESP09L              PIC S9(4) COMP.
           05  RESP09F              PIC X(01).
           05  FILLER REDEFINES RESP09F.
               10  RESP09A          PIC X(01).
           05  RESP09I              PIC X(76).
           05  RESP10L              PIC S9(4) COMP.
           05  RESP10F              PIC X(01).
           05  FILLER REDEFINES RESP10F.
               10  RESP10A          PIC X(01).
           05  RESP10I              PIC X(76).
           05  STATOL               PIC S9(4) COMP.
           05  STATOF               PIC X(01).
           05  FILLER REDEFINES STATOF.
               10  STATOA           PIC X(01).
           05  STATOI               PIC X(40).
           05  MSGOL                PIC S9(4) COMP.
           05  MSGOF                PIC X(01).
           05  FILLER REDEFINES MSGOF.
               10  MSGOA            PIC X(01).
           05  MSGOI                PIC X(78).
      *
       01  AIMAP1O.
           05  FILLER                PIC X(12).
           05  DATEOL               PIC S9(4) COMP.
           05  DATEOF               PIC X(01).
           05  FILLER REDEFINES DATEOF.
               10  DATEOA           PIC X(01).
           05  DATEO                PIC X(8).
           05  QUESTOL              PIC S9(4) COMP.
           05  QUESTOF              PIC X(01).
           05  FILLER REDEFINES QUESTOF.
               10  QUESTOA          PIC X(01).
           05  QUESTO               PIC X(72).
           05  RESP01OL             PIC S9(4) COMP.
           05  RESP01OF             PIC X(01).
           05  FILLER REDEFINES RESP01OF.
               10  RESP01OA         PIC X(01).
           05  RESP01O              PIC X(76).
           05  RESP02OL             PIC S9(4) COMP.
           05  RESP02OF             PIC X(01).
           05  FILLER REDEFINES RESP02OF.
               10  RESP02OA         PIC X(01).
           05  RESP02O              PIC X(76).
           05  RESP03OL             PIC S9(4) COMP.
           05  RESP03OF             PIC X(01).
           05  FILLER REDEFINES RESP03OF.
               10  RESP03OA         PIC X(01).
           05  RESP03O              PIC X(76).
           05  RESP04OL             PIC S9(4) COMP.
           05  RESP04OF             PIC X(01).
           05  FILLER REDEFINES RESP04OF.
               10  RESP04OA         PIC X(01).
           05  RESP04O              PIC X(76).
           05  RESP05OL             PIC S9(4) COMP.
           05  RESP05OF             PIC X(01).
           05  FILLER REDEFINES RESP05OF.
               10  RESP05OA         PIC X(01).
           05  RESP05O              PIC X(76).
           05  RESP06OL             PIC S9(4) COMP.
           05  RESP06OF             PIC X(01).
           05  FILLER REDEFINES RESP06OF.
               10  RESP06OA         PIC X(01).
           05  RESP06O              PIC X(76).
           05  RESP07OL             PIC S9(4) COMP.
           05  RESP07OF             PIC X(01).
           05  FILLER REDEFINES RESP07OF.
               10  RESP07OA         PIC X(01).
           05  RESP07O              PIC X(76).
           05  RESP08OL             PIC S9(4) COMP.
           05  RESP08OF             PIC X(01).
           05  FILLER REDEFINES RESP08OF.
               10  RESP08OA         PIC X(01).
           05  RESP08O              PIC X(76).
           05  RESP09OL             PIC S9(4) COMP.
           05  RESP09OF             PIC X(01).
           05  FILLER REDEFINES RESP09OF.
               10  RESP09OA         PIC X(01).
           05  RESP09O              PIC X(76).
           05  RESP10OL             PIC S9(4) COMP.
           05  RESP10OF             PIC X(01).
           05  FILLER REDEFINES RESP10OF.
               10  RESP10OA         PIC X(01).
           05  RESP10O              PIC X(76).
           05  STATOOL              PIC S9(4) COMP.
           05  STATOOF              PIC X(01).
           05  FILLER REDEFINES STATOOF.
               10  STATOOA          PIC X(01).
           05  STATOO               PIC X(40).
           05  MSGOOL               PIC S9(4) COMP.
           05  MSGOOF               PIC X(01).
           05  FILLER REDEFINES MSGOOF.
               10  MSGOOA           PIC X(01).
           05  MSGOO                PIC X(78).
      *
      * WORKING VARIABLES
      *
       01  WS-VARIABLES.
           05  WS-DATE              PIC X(08).
           05  WS-QUESTION          PIC X(72).
           05  WS-RESPONSE          PIC X(760).
           05  WS-RESPONSE-LINES REDEFINES WS-RESPONSE.
               10  WS-RESP-LINE     PIC X(76) OCCURS 10.
           05  WS-STATUS            PIC X(40).
           05  WS-MSG               PIC X(78).
           05  WS-TD-RECORD         PIC X(80).
           05  WS-TD-LENGTH         PIC S9(4) COMP VALUE 80.
           05  WS-RESP-LENGTH       PIC S9(4) COMP VALUE 760.
           05  WS-WAIT-COUNT        PIC 9(02) VALUE 0.
           05  WS-MAX-WAIT          PIC 9(02) VALUE 10.
      *
      * DFHAID COPY
      *
       01  DFHAID.
           05  DFHNULL              PIC X VALUE X'00'.
           05  DFHENTER             PIC X VALUE ''''.
           05  DFHCLEAR             PIC X VALUE '_'.
           05  DFHPEN               PIC X VALUE '='.
           05  DFHOPID              PIC X VALUE 'W'.
           05  DFHPA1               PIC X VALUE '%'.
           05  DFHPA2               PIC X VALUE '>'.
           05  DFHPA3               PIC X VALUE ','.
           05  DFHPF1               PIC X VALUE '1'.
           05  DFHPF2               PIC X VALUE '2'.
           05  DFHPF3               PIC X VALUE '3'.
           05  DFHPF4               PIC X VALUE '4'.
           05  DFHPF5               PIC X VALUE '5'.
           05  DFHPF6               PIC X VALUE '6'.
           05  DFHPF7               PIC X VALUE '7'.
           05  DFHPF8               PIC X VALUE '8'.
           05  DFHPF9               PIC X VALUE '9'.
           05  DFHPF10              PIC X VALUE ':'.
           05  DFHPF11              PIC X VALUE '#'.
           05  DFHPF12              PIC X VALUE '@'.
      *
       01  DFHBMSCA                 PIC X VALUE X'00'.
      *
       LINKAGE SECTION.
       01  DFHCOMMAREA             PIC X(01).
      *
       PROCEDURE DIVISION.
      *****************************************************************
      * MAIN PROCESSING                                               *
      *****************************************************************
       0000-MAIN.
      *
      * CHECK IF FIRST TIME OR RETURN ENTRY
      *
           IF EIBCALEN = 0
               PERFORM 1000-FIRST-TIME
           ELSE
               MOVE DFHCOMMAREA TO WS-COMMAREA
               PERFORM 2000-PROCESS-INPUT
           END-IF.
      *
           EXEC CICS RETURN
               TRANSID('AIMP')
               COMMAREA(WS-COMMAREA)
               LENGTH(1)
           END-EXEC.
      *
           STOP RUN.
      *
      *****************************************************************
      * FIRST TIME - DISPLAY INITIAL SCREEN                           *
      *****************************************************************
       1000-FIRST-TIME.
      *
           INITIALIZE AIMAP1O.
      *
      * GET CURRENT DATE
      *
           EXEC CICS ASKTIME
               ABSTIME(WS-DATE)
           END-EXEC.
      *
           EXEC CICS FORMATTIME
               ABSTIME(WS-DATE)
               MMDDYY(DATEO)
               DATESEP('/')
           END-EXEC.
      *
           MOVE 'READY - Enter your question'  TO STATOO.
           MOVE SPACES                         TO MSGOO.
      *
           EXEC CICS SEND
               MAP('AIMAP1')
               MAPSET('AIMAPS')
               FROM(AIMAP1O)
               ERASE
               FREEKB
           END-EXEC.
      *
           MOVE 'R' TO WS-COMM-FLAG.
      *
       1000-EXIT.
           EXIT.
      *
      *****************************************************************
      * PROCESS USER INPUT                                            *
      *****************************************************************
       2000-PROCESS-INPUT.
      *
      * RECEIVE MAP INPUT
      *
           EXEC CICS RECEIVE
               MAP('AIMAP1')
               MAPSET('AIMAPS')
               INTO(AIMAP1I)
           END-EXEC.
      *
      * CHECK WHICH KEY WAS PRESSED
      *
           EVALUATE EIBAID
               WHEN DFHPF3
                   PERFORM 3000-EXIT-PROGRAM
               WHEN DFHPF12
                   PERFORM 4000-CLEAR-SCREEN
               WHEN DFHENTER
                   PERFORM 5000-PROCESS-QUESTION
               WHEN OTHER
                   MOVE 'Invalid key pressed' TO WS-MSG
                   PERFORM 6000-SEND-ERROR
           END-EVALUATE.
      *
       2000-EXIT.
           EXIT.
      *
      *****************************************************************
      * EXIT PROGRAM                                                  *
      *****************************************************************
       3000-EXIT-PROGRAM.
      *
           EXEC CICS SEND TEXT
               FROM('AI Assistant ended. Goodbye!')
               LENGTH(30)
               ERASE
               FREEKB
           END-EXEC.
      *
           EXEC CICS RETURN
           END-EXEC.
      *
       3000-EXIT.
           EXIT.
      *
      *****************************************************************
      * CLEAR SCREEN                                                  *
      *****************************************************************
       4000-CLEAR-SCREEN.
      *
           PERFORM 1000-FIRST-TIME.
      *
       4000-EXIT.
           EXIT.
      *
      *****************************************************************
      * PROCESS QUESTION - MAIN AI INTERACTION                        *
      *****************************************************************
       5000-PROCESS-QUESTION.
      *
      * VALIDATE INPUT
      *
           IF QUESTIL = 0 OR QUESTI = SPACES
               MOVE 'Please enter a question' TO WS-MSG
               PERFORM 6000-SEND-ERROR
               GO TO 5000-EXIT
           END-IF.
      *
      * STORE QUESTION
      *
           MOVE QUESTI TO WS-QUESTION.
      *
      * UPDATE STATUS
      *
           MOVE 'Processing your question...' TO STATOO.
      *
      * WRITE QUESTION TO TD QUEUE FOR EXTERNAL PROCESSING
      *
           MOVE SPACES TO WS-TD-RECORD.
           MOVE WS-QUESTION TO WS-TD-RECORD.
      *
           EXEC CICS WRITEQ TD
               QUEUE('AIQO')
               FROM(WS-TD-RECORD)
               LENGTH(WS-TD-LENGTH)
           END-EXEC.
      *
      * WAIT FOR RESPONSE (POLL TD QUEUE)
      * IN PRODUCTION, USE INTERVAL CONTROL OR START COMMAND
      *
           MOVE 0 TO WS-WAIT-COUNT.
           MOVE SPACES TO WS-RESPONSE.
      *
           PERFORM 5100-WAIT-FOR-RESPONSE
               UNTIL WS-WAIT-COUNT >= WS-MAX-WAIT
               OR WS-RESPONSE NOT = SPACES.
      *
      * CHECK IF WE GOT A RESPONSE
      *
           IF WS-RESPONSE = SPACES
               MOVE 'AI service timeout - try again' TO WS-MSG
               PERFORM 6000-SEND-ERROR
               GO TO 5000-EXIT
           END-IF.
      *
      * DISPLAY RESPONSE
      *
           PERFORM 5200-DISPLAY-RESPONSE.
      *
       5000-EXIT.
           EXIT.
      *
      *****************************************************************
      * WAIT FOR AI RESPONSE                                          *
      *****************************************************************
       5100-WAIT-FOR-RESPONSE.
      *
      * DELAY 1 SECOND
      *
           EXEC CICS DELAY
               INTERVAL(1)
           END-EXEC.
      *
      * TRY TO READ RESPONSE FROM TD QUEUE
      *
           EXEC CICS READQ TD
               QUEUE('AIQI')
               INTO(WS-RESPONSE)
               LENGTH(WS-RESP-LENGTH)
               NOHANDLE
           END-EXEC.
      *
           IF EIBRESP NOT = 0
               MOVE SPACES TO WS-RESPONSE
           END-IF.
      *
           ADD 1 TO WS-WAIT-COUNT.
      *
       5100-EXIT.
           EXIT.
      *
      *****************************************************************
      * DISPLAY AI RESPONSE                                           *
      *****************************************************************
       5200-DISPLAY-RESPONSE.
      *
           INITIALIZE AIMAP1O.
      *
      * GET CURRENT DATE
      *
           EXEC CICS ASKTIME
               ABSTIME(WS-DATE)
           END-EXEC.
      *
           EXEC CICS FORMATTIME
               ABSTIME(WS-DATE)
               MMDDYY(DATEO)
               DATESEP('/')
           END-EXEC.
      *
      * PRESERVE QUESTION
      *
           MOVE WS-QUESTION TO QUESTO.
      *
      * MOVE RESPONSE LINES
      *
           MOVE WS-RESP-LINE(1)  TO RESP01O.
           MOVE WS-RESP-LINE(2)  TO RESP02O.
           MOVE WS-RESP-LINE(3)  TO RESP03O.
           MOVE WS-RESP-LINE(4)  TO RESP04O.
           MOVE WS-RESP-LINE(5)  TO RESP05O.
           MOVE WS-RESP-LINE(6)  TO RESP06O.
           MOVE WS-RESP-LINE(7)  TO RESP07O.
           MOVE WS-RESP-LINE(8)  TO RESP08O.
           MOVE WS-RESP-LINE(9)  TO RESP09O.
           MOVE WS-RESP-LINE(10) TO RESP10O.
      *
           MOVE 'Response received - Enter new question' TO STATOO.
           MOVE SPACES TO MSGOO.
      *
           EXEC CICS SEND
               MAP('AIMAP1')
               MAPSET('AIMAPS')
               FROM(AIMAP1O)
               ERASE
               FREEKB
           END-EXEC.
      *
       5200-EXIT.
           EXIT.
      *
      *****************************************************************
      * SEND ERROR MESSAGE                                            *
      *****************************************************************
       6000-SEND-ERROR.
      *
           INITIALIZE AIMAP1O.
      *
           MOVE 'ERROR' TO STATOO.
           MOVE WS-MSG  TO MSGOO.
      *
           EXEC CICS SEND
               MAP('AIMAP1')
               MAPSET('AIMAPS')
               FROM(AIMAP1O)
               DATAONLY
               FREEKB
           END-EXEC.
      *
       6000-EXIT.
           EXIT.
