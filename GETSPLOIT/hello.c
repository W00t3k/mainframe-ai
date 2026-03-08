/*
 * hello.c — Deliberately vulnerable C program for mainframe buffer overflow labs.
 * Source: DC30_Workshop/GETSPLOIT/hello.c
 *
 * Vulnerability: gets() reads into a 150-byte stack buffer with no bounds check.
 * Feed > 150 bytes to overflow the buffer and overwrite the return address.
 *
 * Lab sequence:
 *   Lab 1: Run HELLO normally
 *   Lab 2: Feed 400 bytes (LGTB pattern) -> 0C6 abend
 *   Lab 3: De Bruijn pattern -> find exact return address offset
 *   Lab 4: Craft WTO shellcode -> control execution
 */

#include <string.h>
#include <stdlib.h>
#include <stdio.h>

int main(int argc, char **argv) {
   char buff[150];
   printf("Hi, D3FC0N attendee what is your handle?\n");
   gets(buff);
   printf("Wake up, %s\n\nThe Matrix has you...\n\n", buff);
   printf("Follow the white rabbit.\n\n");
   printf(
"            _________________\n"
"           /            __   \\ \n"
"           |           (__)  | \n"
"           |                 | \n"
"           | .-----.   .--.  | \n"
"           | |     |  /    \\ | \n"
"           | '-----'  \\    / | \n"
"           |           |  |  | \n"
"           | LI DC LI  |  |  | \n"
"           | LI 30 LI  |  |  |Oo \n"
"           | LI LI LI  |  |  |`Oo \n"
"           | LI LI LI  |  |  |  Oo \n"
"           |           |  |  |   Oo \n"
"           | .------. /    \\ |   oO \n"
"           | |      | \\    / |   Oo \n"
"           | '------'  '-oO  |   oO \n"
"           |          .---Oo |   Oo \n"
"           |          ||  ||`Oo  oO \n"
"           |          |'--'| | OoO \n"
"           |          '----' | \n"
"           \\_________________/ \n\n"
"            Ring Ring %s\n\n", buff);
   return 0;
}
