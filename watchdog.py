#!/usr/bin/env python3
"""
Web App Watchdog - DISABLED

This watchdog is disabled because start.sh already includes its own
restart logic and watchdog functionality. Running both causes
conflicts and port binding issues.

Use start.sh to start the web app with integrated watchdog instead.
"""
import sys

if __name__ == "__main__":
    print("=" * 60)
    print("WATCHDOG DISABLED")
    print("=" * 60)
    print("\nThis watchdog has been disabled to avoid conflict with")
    print("start.sh, which already includes integrated watchdog")
    print("functionality and automatic restart logic.")
    print("\nTo start the web app with monitoring, use:")
    print("  ./start.sh")
    print("\nExiting...")
    sys.exit(0)
