/*REXX*/
/* DECODE One Instruction                                             */
/* Ripped from DA.rexx by Andrew J. Armstrong                        */
/* GPL v3 - https://github.com/mainframed/DC30_Workshop               */
/* Usage: TSO DECODEI <hex-instruction>                               */
/* Example: TSO DECODEI 18CF   -> LR R12,R15                         */
trace o
  signal on syntax name onSyntax
  g. = ''
  g.0ARCH = 'Z'
  g.0ARCHNAME = 'z/Architecture'
  call prolog
  call decodeInst arg(1)
return 1

setLoc: procedure expose g.
  arg xLoc
  g.0LOC = x2d(xLoc)
  call nextLoc +0
return

nextLoc: procedure expose g.
  arg nIncrement
  g.0LOC = g.0LOC + nIncrement
  g.0XLOC = d2x(g.0LOC)
  g.0XLOC8 = right(g.0XLOC,8,0)
return

decodeInst: procedure expose g.
  arg 1 aa +2 1 bbbb +4 4 c +1 11 dd +2 0 xInst
  ccc  = aa || c
  dddd = aa || dd
  select
    when g.0INST.1.aa   <> '' then xOpCode = aa
    when g.0INST.2.bbbb <> '' then xOpCode = bbbb
    when g.0INST.3.ccc  <> '' then xOpCode = ccc
    when g.0INST.4.dddd <> '' then xOpCode = dddd
    otherwise xOpCode = '.'
  end
  if xOpCode <> '.'
  then g.0INST = g.0INST + 1
  else g.0TODO = g.0TODO + 1
  sMnemonic = g.0INST.1.xOpCode
  if sMnemonic = '' then sMnemonic = '???'
  sDesc     = g.0DESC.xOpCode
  say xInst '->' sMnemonic sDesc
return

onSyntax:
  say 'Syntax error - usage: DECODEI <hex-instruction>'
  say 'Example: DECODEI 18CF'
return

prolog:
  g.0INST.1.18 = 'LR'  ; g.0DESC.18 = 'Load Register'
  g.0INST.1.1A = 'AR'  ; g.0DESC.1A = 'Add Register'
  g.0INST.1.1B = 'SR'  ; g.0DESC.1B = 'Subtract Register'
  g.0INST.1.1C = 'MR'  ; g.0DESC.1C = 'Multiply Register'
  g.0INST.1.1D = 'DR'  ; g.0DESC.1D = 'Divide Register'
  g.0INST.1.1E = 'ALR' ; g.0DESC.1E = 'Add Logical Register'
  g.0INST.1.1F = 'SLR' ; g.0DESC.1F = 'Subtract Logical Register'
  g.0INST.1.10 = 'LPR' ; g.0DESC.10 = 'Load Positive Register'
  g.0INST.1.11 = 'LNR' ; g.0DESC.11 = 'Load Negative Register'
  g.0INST.1.12 = 'LTR' ; g.0DESC.12 = 'Load and Test Register'
  g.0INST.1.13 = 'LCR' ; g.0DESC.13 = 'Load Complement Register'
  g.0INST.1.14 = 'NR'  ; g.0DESC.14 = 'AND Register'
  g.0INST.1.15 = 'CLR' ; g.0DESC.15 = 'Compare Logical Register'
  g.0INST.1.16 = 'OR'  ; g.0DESC.16 = 'OR Register'
  g.0INST.1.17 = 'XR'  ; g.0DESC.17 = 'Exclusive OR Register'
  g.0INST.1.05 = 'BALR'; g.0DESC.05 = 'Branch and Link Register'
  g.0INST.1.06 = 'BCTR'; g.0DESC.06 = 'Branch on Count Register'
  g.0INST.1.07 = 'BCR' ; g.0DESC.07 = 'Branch on Condition Register'
  g.0INST.1.0A = 'SVC' ; g.0DESC.0A = 'Supervisor Call'
  g.0INST.1.0D = 'BASR'; g.0DESC.0D = 'Branch and Save Register'
  g.0INST.1.40 = 'STH' ; g.0DESC.40 = 'Store Halfword'
  g.0INST.1.41 = 'LA'  ; g.0DESC.41 = 'Load Address'
  g.0INST.1.42 = 'STC' ; g.0DESC.42 = 'Store Character'
  g.0INST.1.43 = 'IC'  ; g.0DESC.43 = 'Insert Character'
  g.0INST.1.44 = 'EX'  ; g.0DESC.44 = 'Execute'
  g.0INST.1.45 = 'BAL' ; g.0DESC.45 = 'Branch and Link'
  g.0INST.1.46 = 'BCT' ; g.0DESC.46 = 'Branch on Count'
  g.0INST.1.47 = 'BC'  ; g.0DESC.47 = 'Branch on Condition'
  g.0INST.1.48 = 'LH'  ; g.0DESC.48 = 'Load Halfword'
  g.0INST.1.49 = 'CH'  ; g.0DESC.49 = 'Compare Halfword'
  g.0INST.1.4A = 'AH'  ; g.0DESC.4A = 'Add Halfword'
  g.0INST.1.4B = 'SH'  ; g.0DESC.4B = 'Subtract Halfword'
  g.0INST.1.4C = 'MH'  ; g.0DESC.4C = 'Multiply Halfword'
  g.0INST.1.4D = 'BAS' ; g.0DESC.4D = 'Branch and Save'
  g.0INST.1.4E = 'CVD' ; g.0DESC.4E = 'Convert to Decimal'
  g.0INST.1.4F = 'CVB' ; g.0DESC.4F = 'Convert to Binary'
  g.0INST.1.50 = 'ST'  ; g.0DESC.50 = 'Store'
  g.0INST.1.54 = 'N'   ; g.0DESC.54 = 'AND'
  g.0INST.1.55 = 'CL'  ; g.0DESC.55 = 'Compare Logical'
  g.0INST.1.56 = 'O'   ; g.0DESC.56 = 'OR'
  g.0INST.1.57 = 'X'   ; g.0DESC.57 = 'Exclusive OR'
  g.0INST.1.58 = 'L'   ; g.0DESC.58 = 'Load'
  g.0INST.1.59 = 'C'   ; g.0DESC.59 = 'Compare'
  g.0INST.1.5A = 'A'   ; g.0DESC.5A = 'Add'
  g.0INST.1.5B = 'S'   ; g.0DESC.5B = 'Subtract'
  g.0INST.1.5C = 'M'   ; g.0DESC.5C = 'Multiply'
  g.0INST.1.5D = 'D'   ; g.0DESC.5D = 'Divide'
  g.0INST.1.5E = 'AL'  ; g.0DESC.5E = 'Add Logical'
  g.0INST.1.5F = 'SL'  ; g.0DESC.5F = 'Subtract Logical'
  g.0INST.1.D2 = 'MVC' ; g.0DESC.D2 = 'Move Character'
  g.0INST.1.D5 = 'CLC' ; g.0DESC.D5 = 'Compare Logical Character'
  g.0INST.1.D4 = 'NC'  ; g.0DESC.D4 = 'AND Character'
  g.0INST.1.D6 = 'OC'  ; g.0DESC.D6 = 'OR Character'
  g.0INST.1.D7 = 'XC'  ; g.0DESC.D7 = 'Exclusive OR Character'
  g.0INST.1.F2 = 'PACK'; g.0DESC.F2 = 'Pack'
  g.0INST.1.F3 = 'UNPK'; g.0DESC.F3 = 'Unpack'
  g.0INST.1.FA = 'AP'  ; g.0DESC.FA = 'Add Decimal'
  g.0INST.1.FB = 'SP'  ; g.0DESC.FB = 'Subtract Decimal'
  g.0INST.1.FC = 'MP'  ; g.0DESC.FC = 'Multiply Decimal'
  g.0INST.1.FD = 'DP'  ; g.0DESC.FD = 'Divide Decimal'
return
