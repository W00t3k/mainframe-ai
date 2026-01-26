SoftDevLabs (SDL) Hercules 4.x Hyperion Binaries For TK4- (Snapshot 2020-05-24)
===============================================================================

Starting with Update 09, the MVS 3.8j Tur(n)key 4- system (TK4-) will no longer
come with its own specialized version of the Hercules System/370, ESA/390, and
z/Architecture Emulator. SoftDevLabs (SDL) Hercules 4.2 Hyperion and later
versions fully support TK4-, making the specialized version obsolete.

This package contains a set of SDL-Hyperion binaries built between 2020-05-13
and 2020-05-24:

o Windows 32/64-bit platforms
o Linux 32/64-bit Intel platforms
o Linux 32-bit ARM softfloat and hardfloat platforms
o Linux 64-bit ARM aarch64 platform
o OS X 64-bit Intel platform

Please note, that the OS X 32-bit Intel platform is no longer supported. Do not
install this package, if you are still using an OS X 32-bit OS on a 32-bit only
machine.


Important Notice (I)
--------------------

To install this package on an existing TK4- system, it must already be enabled
for SDL Hyperion. Starting with Update 09, TK4- is generally enabled for SDL
Hyperion. Earlier versions must be enabled explicitely. If your system is not
yet enabled, please install the package found at

https://polybox.ethz.ch/index.php/s/sZk2wRMhsF2uwai/download

If you are not sure, whether your system is SDL Hyperion enabled, verify the
existence of folder tk4-/hercules_pre_SDL: If it exists, your system is enabled.
If it doesn't exist, you need to install the above package to enable it.


Important Notice (II)
---------------------

These binaries contain a version of Peter Coghlan's TCPNJE driver that is
functionally equivalent to the one distributed with Bob Polmanter's NJE38
product. So, after installation of the binaries, NJE38 can be installed on
the TK4- MVS 3.8j system without needing to rebuild Hercules. If you intend
to use NJE38, simply skip the steps in the installation instructions that
deal with rebuilding Hercules.

This package installs file tk4-/local_conf/tcpnje as a central location for the
definition of TCPNJE connections. If your system has this file already and if
you made any changes to the initial version, please save the changed file and
restore it after installation of this package. If you intend to use the TCPNJE
driver, follow the comments in this file to define TCPNJE links to the NJE
neighbours of your system. See also Step "3. Define BSC connections in Hercules
to connect with a remote NJE partner." in chapter "Detailed Step-by-Step" in
Bob's "NJE 38 Installation and Use Guide" for details on the parameters to be
entered in this file.

Thanks to Peter Coghlan for making TCPNJE available to the TK4- MVS 3.8j
community!


Installation:
-------------

1. Perform a complete backup of your existing TK4- system.

2. Read the above important notice (I) and enable your system for SDL Hyperion
   if it isn't already enabled.

3. Read the above important notice (II) and act accordingly if necessary.

4. Unzip SDL_Hercules_Hyperion_4.3.9999_build_for_TK4-_Snapshot_1010-05-24.zip
   into the tk4- folder. Make sure to allow the unzip utility to merge with
   existing folders and to replace existing files.


--------
J. Winkelmann, May 24, 2020 -- winkelmann@id.ethz.ch
