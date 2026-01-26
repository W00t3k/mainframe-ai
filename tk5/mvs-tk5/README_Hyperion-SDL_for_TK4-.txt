SoftDevLabs (SDL) Hercules 4.2 Hyperion Binaries For TK4-
=========================================================

Starting with Update 09, the MVS 3.8j Tur(n)key 4- system (TK4-) will no longer
come with its own specialized version of the Hercules System/370, ESA/390, and
z/Architecture Emulator. SoftDevLabs (SDL) Hercules 4.2 Hyperion and later
versions fully support TK4-, making the specialized version obsolete.

This package contains a complete set of SDL-Hyperion binaries for all platforms
previously supported by the specialized Hercules version:

o Windows 32/64-bit platforms
o Linux 32/64-bit Intel platforms
o Linux 32-bit ARM softfloat and hardfloat platforms
o OS X 32/64-bit Intel platforms

In addition, support for the 64-bit ARM platform aarch64 has been added.

SDL-Hyperion requires some minor changes to configuration files and automation
scripting, which are also included in this package.


Installation:
-------------

1. Perform a complete backup of your existing TK4- system.

2. Unzip file Hyperion-SDL_for_TK4-.zip into the tk4- folder. Make sure to
   allow the unzip utility to merge with existing folders and to replace
   existing files.

3. a) On Windows systems run activate_SDL.bat from the tk4- folder, either
      using a command window or by (single or double) clicking it from an
      explorer window.
   b) On all other systems run activate_SDL from the tk4- folder.

   Note: Running deactivate_SDL/activate_SDL alternately will deactivate/
         reactivate the SDL-Hyperion binaries.

4. If you applied any changes to tk4-/mvs, tk4-/mvs.bat, tk4-/conf/tk4-.cnf,
   tk4-/conf/tk4-_updates/03, tk4-/conf/tk4-_specific02.cnf or
   tk4-/conf/tk4-_default.cnf, re-apply them to the new files. As a reference,
   your original files are still available with "_pre_SDL" appended to the
   filename. Note however, that none of these files is intended to be modified
   by the user. You may want to consider changing only files in the local_conf
   or local_scripts folders instead of any of the above.


Deactivation:
-------------

To reactivate the binaries that were in use before installing the SDL ones, run
deactivate_SDL.bat (Windows) or deactivate_SDL (Linux or OS X) from the tk4-
folder.

Note: Running activate_SDL/deactivate_SDL alternately will reactivate/deactivate
      the SDL-Hyperion binaries.


Usage Notes:
------------

Except for the differences listed here, usage of the TK4- system with the SDL-
Hyperion binaries is exactly the same than with the original TK4- ones.

o Unattended Mode Without Hercules Console:

  When running TK4- in unattended mode without a Hercules console (aka "Daemon
  Mode", the default TK4- mode of operation), with TK4- Hercules the console log
  is displayed in the shell or cmd window from which the mvs/mvs.bat scripts are
  executed. Due to a different handling of stdin and stdout in SDL-Hyperion, the
  way this functionality had been implemented originally, needed to be changed:

  Windows:    The cmd window running the mvs.bat script is closed immediately.
              A few seconds later a WinTail window displaying the console log
              comes up. After automatic shutdown of TK4- and Hercules power off
              the WinTail Window remains open. It can be used to further
              inspect the console log. If no longer needed, it should be closed
              explicitely.

              This functionality relies on two free utilities, which are
              provided as a convenience in tk4-/hercules/windows/utils:

              - WinTail by Alberto Andreo (http://www.tailforwindows.net)
              - Quiet by Joe Richards (http://www.joeware.net)

  Linux, OSX: The specific requirements of SDL-Hyperion's daemon mode are
              covered using the coprocess support of the bash shell. The user
              experience is exactly the same as it was with TK4- Hercules.

              As the functionality depends on bash's coprocess support, bash
              version 4.0 or higher is now required to execute the mvs script.
              This version was first released some ten years ago, so one can
              assume that it is available on most Linux systems currently being
              in use.

              On OSX systems, however, bash version 4 or higher is not available
              and will probably not become available for quite some time. The
              reason for this is that Apple doesn't comply with the GPLv3
              license used by bash since version 4.0. The well known package
              managers for OSX (MacPorts and Homebrew) provide bash version 4,
              but as long as those are not installed in /usr/bin (replacing
              Apples old version) it is difficult to use them by just calling
              a script from the command line. To work around this problem,
              a sufficiently recent version of bash is provided in
              tk4-/hercules/darwin/utils and the mvs script has been redesigned
              to use this version of bash when running on OSX. This is fully
              transparent to the user, but it might nonetheless be good to
              know, just in case problems would come up.

o Facility Management:

  In S/370 mode, the TK4- version of Hercules features the following
  functionality which is not part of the standard S/370 architecure:

  - S/370 Instruction Extension Facility
  - Message Security Assist Extension 1, 2, 3 and 4
  - TCPIP Extension (X'75' Instruction)

  This functionality is also available with SDL-Hyperion. Implementation and
  usage differ, however: In TK4- Hercules the underlying facilities are hard
  coded, while SDL-Hyperion employs a dynamic facility management. The
  following table summarizes the resulting usage differences:

                   +---------------------------------+-------------------------
                   |          TK4- Hercules          |      SDL-Hyperion
                   +----------------+----------------+-------------------------
                   |   enable cmd   |  disable cmd   | facility enable/disable
  -----------------+----------------+----------------+-------------------------
  S/370 Extension  | ldmod s37x     | rmmod s37x     | HERC_370_EXTENSION
  -----------------+----------------+----------------+-------------------------
  Security Assists | ldmod dyncrypt | rmmod dyncrypt | 017_MSA
                   |                |                | 076_MSA_EXTENSION_3
                   |                |                | 077_MSA_EXTENSION_4
                   |                |                | HERC_MSA_EXTENSION_1
                   |                |                | HERC_MSA_EXTENSION_2
  -----------------+----------------+----------------+-------------------------
  TCPIP Extension  |          always enabled         | HERC_TCPIP_EXTENSION
                   |                                 | HERC_TCPIP_PROB_STATE
  -----------------+---------------------------------+-------------------------

  To enable the additional functionality on TK4- Hercules the commands in
  the "enable cmd" column need to be issued, while on SDL-Hyperion the
  facilities listed in the "facility enable/disable" need to be enabled.

  Presumably, many (if not most) current TK4- users have the additional
  functionality enabled. Thus this level of functionality is now enabled
  by default when starting Hercules using the mvs/mvs.bat or start_herc/
  start_herc.bat scripts.

  Note: If the execution of the "ldmod s37x" and "ldmod dyncrypt" commands were
  ----- explicitely automated in tk4-.parm or elsewhere, it is recommended to
        remove this automation when using the SDL-Hyperion binaries.


--------
J. Winkelmann, March 28, 2019 -- winkelmann@id.ethz.ch
