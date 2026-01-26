#!/usr/bin/env python3
"""
Integration with Mainframed's Security Tools
Attribution: Tools by Soldier of FORTRAN (@mainframed767)
Repository: https://github.com/mainframed

This module provides integration and launching capabilities for mainframed's
comprehensive suite of mainframe security testing tools.
"""

import os
import subprocess
import sys
from datetime import datetime
from ..utils.logger import log_info, log_warning, log_error


class MainframedIntegration:
    """
    Integration with mainframed's security tools
    
    Attribution:
        Tools by: Soldier of FORTRAN (@mainframed767)
        GitHub: https://github.com/mainframed
        Blog: http://mainframed767.tumblr.com/
    """
    
    def __init__(self, tools_path=None):
        """
        Initialize mainframed tools integration
        
        Args:
            tools_path: Path to mainframed tools directory (optional)
        """
        if tools_path:
            self.tools_path = tools_path
        else:
            # Default to mainframed_tools in BIRP directory
            birp_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.tools_path = os.path.join(birp_dir, 'mainframed_tools')
        self.attribution = {
            'author': 'Soldier of FORTRAN (@mainframed767)',
            'github': 'https://github.com/mainframed',
            'blog': 'http://mainframed767.tumblr.com/'
        }
        
        # Tool definitions
        self.tools = {
            'hack3270': {
                'name': 'hack3270',
                'description': 'Python3 tool to manipulate TN3270 data streams for CICS application testing',
                'repo': 'https://github.com/mainframed/hack3270',
                'type': 'python',
                'command': 'hack3270'
            },
            'nmap-scripts': {
                'name': 'NMAP TN3270 Scripts',
                'description': 'NMAP scripts for TN3270 interaction, TSO enumeration, and brute force',
                'repo': 'https://github.com/mainframed/nmap-scripts',
                'type': 'nmap',
                'scripts': [
                    'tso-enum.nse',
                    'tso-brute.nse',
                    'tn3270-screen.nse',
                    'tn3270-hidden.nse',
                    'cics-enum.nse',
                    'cics-info.nse'
                ]
            },
            'enumeration': {
                'name': 'z/OS Enumeration',
                'description': 'REXX script to enumerate z/OS system information',
                'repo': 'https://github.com/mainframed/Enumeration',
                'type': 'rexx',
                'file': 'Rexx_InfoScript.rx'
            },
            'tshocker': {
                'name': 'TShOcker',
                'description': 'Privilege escalation exploit for z/OS',
                'repo': 'https://github.com/mainframed/TShOcker',
                'type': 'exploit'
            },
            'privesc': {
                'name': 'Privesc',
                'description': 'Privilege escalation scripts for z/OS',
                'repo': 'https://github.com/mainframed/Privesc',
                'type': 'exploit'
            },
            'mfscreen': {
                'name': 'MFScreen',
                'description': 'Tool to take screenshots of CICS transactions',
                'repo': 'https://github.com/mainframed/MFScreen',
                'type': 'python'
            },
            'mfsniffer': {
                'name': 'MFSniffer',
                'description': 'Mainframe network traffic sniffer',
                'repo': 'https://github.com/mainframed/MFSniffer',
                'type': 'python'
            },
            'setn3270': {
                'name': 'SETn3270',
                'description': 'TN3270 MitM proxy and manipulation tool',
                'repo': 'https://github.com/mainframed/SETn3270',
                'type': 'python'
            },
            'catmap': {
                'name': 'CATMAP',
                'description': 'Catalog mapper for z/OS datasets',
                'repo': 'https://github.com/mainframed/CATMAP',
                'type': 'rexx'
            },
            'dvca': {
                'name': 'DVCA',
                'description': 'Damn Vulnerable CICS Application for testing',
                'repo': 'https://github.com/mainframed/DVCA',
                'type': 'cics'
            },
            'ansi2ebcdic': {
                'name': 'ANSi2EBCDiC',
                'description': 'Convert ANSI to EBCDIC encoding',
                'repo': 'https://github.com/mainframed/ANSi2EBCDiC',
                'type': 'python'
            },
            'ansi2bms': {
                'name': 'ANSi2BMS',
                'description': 'Convert ANSI to BMS (Basic Mapping Support)',
                'repo': 'https://github.com/mainframed/ANSi2BMS',
                'type': 'python'
            }
        }
    
    def print_attribution(self):
        """Print attribution information"""
        print("\n" + "=" * 70)
        print("Mainframed Security Tools Integration")
        print("=" * 70)
        print(f"Tools by: {self.attribution['author']}")
        print(f"GitHub:   {self.attribution['github']}")
        print(f"Blog:     {self.attribution['blog']}")
        print("=" * 70 + "\n")
    
    def list_tools(self):
        """List all available mainframed tools"""
        self.print_attribution()
        
        print("Available Tools:\n")
        for tool_id, tool_info in self.tools.items():
            print(f"  [{tool_id}]")
            print(f"    Name: {tool_info['name']}")
            print(f"    Description: {tool_info['description']}")
            print(f"    Repository: {tool_info['repo']}")
            print(f"    Type: {tool_info['type']}")
            print()
    
    def check_tool_installed(self, tool_id):
        """Check if a tool is installed"""
        if tool_id not in self.tools:
            return False
        
        tool = self.tools[tool_id]
        tool_path = os.path.join(self.tools_path, tool_id)
        
        return os.path.exists(tool_path)
    
    def install_tool(self, tool_id):
        """
        Install a mainframed tool via git clone
        
        Args:
            tool_id: Tool identifier
        """
        if tool_id not in self.tools:
            log_error(f"Unknown tool: {tool_id}")
            return False
        
        tool = self.tools[tool_id]
        tool_path = os.path.join(self.tools_path, tool_id)
        
        # Create tools directory if it doesn't exist
        os.makedirs(self.tools_path, exist_ok=True)
        
        if os.path.exists(tool_path):
            log_info(f"{tool['name']} is already installed at {tool_path}")
            return True
        
        log_info(f"Installing {tool['name']} from {tool['repo']}...")
        
        try:
            subprocess.run(
                ['git', 'clone', tool['repo'], tool_path],
                check=True,
                capture_output=True
            )
            log_info(f"Successfully installed {tool['name']}")
            return True
        except subprocess.CalledProcessError as e:
            log_error(f"Failed to install {tool['name']}: {e}")
            return False
    
    def launch_hack3270(self, target=None, proxy_port=2323, args=None):
        """
        Launch hack3270 tool
        
        Args:
            target: Target host:port
            proxy_port: Local proxy port (default: 2323)
            args: Additional arguments
        """
        self.print_attribution()
        
        tool_path = os.path.join(self.tools_path, 'hack3270')
        
        if not os.path.exists(tool_path):
            log_warning("hack3270 not installed. Installing...")
            if not self.install_tool('hack3270'):
                return False
        
        cmd = ['python3', os.path.join(tool_path, 'hack3270.py')]
        
        # Add proxy port if specified
        if proxy_port:
            cmd.extend(['-p', str(proxy_port)])
        
        # Use unique project name to avoid loading old configs
        from datetime import datetime
        project_name = f"birpv2_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        cmd.extend(['-n', project_name])
        
        if target:
            # hack3270.py expects IP and PORT as separate positional arguments
            if ':' in target:
                host, port = target.split(':', 1)
                cmd.extend([host, port])
            else:
                log_error("Target must be in format host:port")
                return False
        
        if args:
            cmd.extend(args)
        
        log_info(f"Launching hack3270: {' '.join(cmd)}")
        
        try:
            subprocess.run(cmd)
            return True
        except Exception as e:
            log_error(f"Failed to launch hack3270: {e}")
            return False
    
    def run_nmap_script(self, script_name, target, args=None):
        """
        Run mainframed NMAP script
        
        Args:
            script_name: Name of the NSE script
            target: Target host
            args: Additional nmap arguments
        """
        self.print_attribution()
        
        tool_path = os.path.join(self.tools_path, 'nmap-scripts')
        
        if not os.path.exists(tool_path):
            log_warning("nmap-scripts not installed. Installing...")
            if not self.install_tool('nmap-scripts'):
                return False
        
        script_path = os.path.join(tool_path, script_name)
        
        if not os.path.exists(script_path):
            log_error(f"Script {script_name} not found")
            return False
        
        cmd = ['nmap', '--script', script_path, '-p', '23', target]
        
        if args:
            cmd.extend(args)
        
        log_info(f"Running NMAP script: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            print(result.stdout)
            return True
        except Exception as e:
            log_error(f"Failed to run NMAP script: {e}")
            return False
    
    def tso_enumerate(self, target, userlist=None, commands=''):
        """
        Run TSO user enumeration
        
        Args:
            target: Target host
            userlist: Path to user list file
            commands: Commands to access TSO (default: 'logon applid(tso)')
        """
        self.print_attribution()
        log_info(f"Running TSO enumeration against {target}")
        
        script_args = []
        # Always add commands argument, even if empty
        script_args.append(f"tso-enum.commands='{commands}'")
        if userlist:
            script_args.append(f'userdb={userlist}')
        
        args = []
        if script_args:
            args.extend(['--script-args', ','.join(script_args)])
        
        return self.run_nmap_script('tso-enum.nse', target, args)
    
    def tso_brute_force(self, target, userlist=None, passlist=None, commands=''):
        """
        Run TSO brute force attack
        
        Args:
            target: Target host
            userlist: Path to user list file
            passlist: Path to password list file
            commands: Commands to access TSO (default: 'logon applid(tso)')
        """
        self.print_attribution()
        log_info(f"Running TSO brute force against {target}")
        
        script_args = []
        # Always add commands argument, even if empty
        script_args.append(f"tso-brute.commands='{commands}'")
        if userlist:
            script_args.append(f'userdb={userlist}')
        if passlist:
            script_args.append(f'passdb={passlist}')
        
        args = []
        if script_args:
            args.extend(['--script-args', ','.join(script_args)])
        
        return self.run_nmap_script('tso-brute.nse', target, args)
    
    def cics_enumerate(self, target, commands='cics'):
        """
        Run CICS transaction enumeration
        
        Args:
            target: Target host
            commands: Commands to access CICS (default: 'cics')
        
        Note: TK4- does not have CICS installed by default.
              This tool requires a mainframe with CICS.
        """
        self.print_attribution()
        log_info(f"Running CICS enumeration against {target}")
        log_warning("Note: TK4- does not have CICS installed. This will only work on mainframes with CICS.")
        
        args = []
        if commands:
            args.extend(['--script-args', f"cics-enum.commands='{commands}'"])
        
        return self.run_nmap_script('cics-enum.nse', target, args)
    
    def grab_screen(self, target):
        """
        Grab TN3270 screen
        
        Args:
            target: Target host
        """
        self.print_attribution()
        log_info(f"Grabbing screen from {target}")
        
        return self.run_nmap_script('tn3270-screen.nse', target)
    
    def find_hidden_fields(self, target):
        """
        Find hidden fields on TN3270 screen
        
        Args:
            target: Target host
        """
        self.print_attribution()
        log_info(f"Finding hidden fields on {target}")
        
        return self.run_nmap_script('tn3270-hidden.nse', target)
    
    def launch_setn3270(self, listen_port=3270, target=None):
        """
        Launch SETn3270 MitM proxy
        
        Args:
            listen_port: Port to listen on
            target: Target mainframe to proxy to
        """
        self.print_attribution()
        
        tool_path = os.path.join(self.tools_path, 'setn3270')
        
        if not os.path.exists(tool_path):
            log_warning("SETn3270 not installed. Installing...")
            if not self.install_tool('setn3270'):
                return False
        
        cmd = ['python3', os.path.join(tool_path, 'setn3270.py')]
        cmd.extend(['-l', str(listen_port)])
        
        if target:
            cmd.extend(['-t', target])
        
        log_info(f"Launching SETn3270: {' '.join(cmd)}")
        
        try:
            subprocess.run(cmd)
            return True
        except Exception as e:
            log_error(f"Failed to launch SETn3270: {e}")
            return False
    
    def launch_mfsniffer(self, interface='eth0', ip_address=None, port='23'):
        """
        Launch MFSniffer
        
        Args:
            interface: Network interface to sniff on (default: 'eth0', use 'lo0' for localhost)
            ip_address: Target mainframe IP address to monitor
            port: Target mainframe port (default: '23')
        """
        self.print_attribution()
        
        tool_path = os.path.join(self.tools_path, 'mfsniffer')
        
        if not os.path.exists(tool_path):
            log_warning("MFSniffer not installed. Installing...")
            if not self.install_tool('mfsniffer'):
                return False
        
        if not ip_address:
            log_error("IP address is required for MFSniffer")
            return False
        
        cmd = ['sudo', 'python3', os.path.join(tool_path, 'mfsniffer.py')]
        cmd.extend(['-i', interface, '-a', ip_address, '-p', str(port)])
        
        log_info(f"Launching MFSniffer: {' '.join(cmd)}")
        log_warning("MFSniffer requires root/sudo privileges")
        
        try:
            subprocess.run(cmd)
            return True
        except Exception as e:
            log_error(f"Failed to launch MFSniffer: {e}")
            return False
    
    def show_privesc_examples(self):
        """Show Privesc exploit examples and usage"""
        self.print_attribution()
        
        print("\n" + "=" * 70)
        print("Privesc Scripts - Privilege Escalation Exploits")
        print("=" * 70)
        print("\n⚠️  Use only on systems you have authorization to test\n")
        
        examples = """
Available Exploits (upload and run on target mainframe):

1. APF Authorization Exploits:
   - apflist.jcl          - List APF authorized libraries
   - apfadd.jcl           - Add library to APF list
   - apftest.rexx         - Test APF authorization
   
   Example Usage:
   • Upload apflist.jcl to mainframe
   • Submit via TSO: SUBMIT 'YOUR.DATASET(APFLIST)'
   • Check output for authorized libraries

2. RACF/Security Exploits:
   - racfadm.rexx         - RACF admin privilege escalation
   - bypass_racf.jcl      - Attempt RACF bypass
   - permit_all.rexx      - Grant permissions
   
   Example Usage:
   • Upload racfadm.rexx to 'YOUR.REXX.EXEC'
   • Run from TSO: EX 'YOUR.REXX.EXEC(RACFADM)'
   • Check for elevated privileges

3. Dataset Access Exploits:
   - dataset_copy.jcl     - Copy protected datasets
   - catalog_update.rexx  - Modify catalog entries
   - uncatalog.jcl        - Uncatalog/recatalog datasets
   
   Example Usage:
   • Edit dataset_copy.jcl with target dataset names
   • Submit job and check for successful copy
   • Access previously restricted data

4. Job Submission Exploits:
   - submit_as_user.jcl   - Submit job as different user
   - job_intercept.rexx   - Intercept job output
   - spool_read.jcl       - Read spool files
   
   Example Usage:
   • Modify submit_as_user.jcl with target userid
   • Submit and verify job runs with elevated privileges

5. System Command Exploits:
   - operator_cmd.rexx    - Issue operator commands
   - console_access.jcl   - Access system console
   - modify_cmd.rexx      - Modify system parameters
   
   Example Usage:
   • Upload operator_cmd.rexx
   • Execute: EX 'YOUR.REXX.EXEC(OPERATOR)'
   • Issue privileged operator commands

How to Use:
1. Browse scripts: ls mainframed_tools/privesc/
2. Review script for your target system
3. Upload to mainframe via FTP/IND$FILE
4. Execute via TSO, batch, or CICS
5. Check output for success/failure

Note: These are exploit scripts to run ON the mainframe,
      not tools to run FROM your workstation.
"""
        print(examples)
        print("=" * 70 + "\n")
    
    def install_all_tools(self):
        """Install all mainframed tools"""
        self.print_attribution()
        log_info("Installing all mainframed tools...")
        
        for tool_id in self.tools.keys():
            log_info(f"Installing {tool_id}...")
            self.install_tool(tool_id)
        
        log_info("Installation complete!")
    
    def generate_tool_report(self):
        """Generate a report of installed tools"""
        self.print_attribution()
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'attribution': self.attribution,
            'tools': {}
        }
        
        for tool_id, tool_info in self.tools.items():
            installed = self.check_tool_installed(tool_id)
            report['tools'][tool_id] = {
                'name': tool_info['name'],
                'description': tool_info['description'],
                'repository': tool_info['repo'],
                'installed': installed,
                'path': os.path.join(self.tools_path, tool_id) if installed else None
            }
        
        return report


def main():
    """CLI interface for mainframed tools"""
    integration = MainframedIntegration()
    
    print("""
Mainframed Security Tools Integration
======================================

1. List all tools
2. Install tool
3. Install all tools
4. Launch hack3270
5. TSO User Enumeration
6. TSO Brute Force
7. CICS Enumeration
8. Grab TN3270 Screen
9. Find Hidden Fields
10. Launch SETn3270 Proxy
11. Launch MFSniffer
12. Show Privesc Exploit Examples
13. Generate Tool Report

Enter choice: """, end='')
    
    choice = input().strip()
    
    if choice == '1':
        integration.list_tools()
    elif choice == '2':
        tool_id = input("Enter tool ID: ").strip()
        integration.install_tool(tool_id)
    elif choice == '3':
        integration.install_all_tools()
    elif choice == '4':
        target = input("Enter target host:port (default: 127.0.0.1:23): ").strip() or '127.0.0.1:23'
        proxy_port = input("Enter local proxy port (default: 2323): ").strip() or '2323'
        integration.launch_hack3270(target, proxy_port=int(proxy_port))
    elif choice == '5':
        target = input("Enter target (default: 127.0.0.1): ").strip() or '127.0.0.1'
        userlist = input("Enter userlist file (default: users.txt): ").strip() or 'mainframed_tools/users.txt'
        commands = input("Enter TSO commands (press Enter for none): ").strip()
        integration.tso_enumerate(target, userlist=userlist, commands=commands)
    elif choice == '6':
        target = input("Enter target (default: 127.0.0.1): ").strip() or '127.0.0.1'
        userlist = input("Enter userlist file (default: users.txt): ").strip() or 'mainframed_tools/users.txt'
        passlist = input("Enter passlist file (default: passwords.txt): ").strip() or 'mainframed_tools/passwords.txt'
        commands = input("Enter TSO commands (press Enter for none): ").strip()
        integration.tso_brute_force(target, userlist=userlist, passlist=passlist, commands=commands)
    elif choice == '7':
        target = input("Enter target (default: 127.0.0.1): ").strip() or '127.0.0.1'
        commands = input("Enter CICS commands (default: cics): ").strip() or 'cics'
        integration.cics_enumerate(target, commands=commands)
    elif choice == '8':
        target = input("Enter target (default: 127.0.0.1): ").strip() or '127.0.0.1'
        integration.grab_screen(target)
    elif choice == '9':
        target = input("Enter target (default: 127.0.0.1): ").strip() or '127.0.0.1'
        userlist = input("Enter userlist file (default: users.txt): ").strip() or '/Users/w00tock/mainframed_tools/users.txt'
        integration.find_hidden_fields(target)
    elif choice == '10':
        target = input("Enter target mainframe (default: 127.0.0.1): ").strip() or '127.0.0.1'
        integration.launch_setn3270(target=target)
    elif choice == '11':
        interface = input("Enter network interface (default: lo0): ").strip() or 'lo0'
        ip_address = input("Enter mainframe IP address (default: 127.0.0.1): ").strip() or '127.0.0.1'
        port = input("Enter port (default: 23): ").strip() or '23'
        integration.launch_mfsniffer(interface, ip_address, port)
    elif choice == '12':
        integration.show_privesc_examples()
    elif choice == '13':
        report = integration.generate_tool_report()
        print("\nTool Report:")
        for tool_id, info in report['tools'].items():
            status = "✓ Installed" if info['installed'] else "✗ Not installed"
            print(f"  {tool_id}: {status}")
    else:
        print("Invalid choice")


if __name__ == '__main__':
    main()
