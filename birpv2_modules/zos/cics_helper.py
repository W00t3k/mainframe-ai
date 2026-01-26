#!/usr/bin/env python3
"""
CICS (Customer Information Control System) Helper for z/OS
Transaction processing and CICS-specific utilities
"""

import re

class CICSHelper:
    """Helper for CICS transaction processing"""
    
    def __init__(self):
        self.trans_pattern = re.compile(r'[A-Z0-9]{4}')
        
    def detect_cics_screen(self, screen_text):
        """Detect if current screen is CICS"""
        cics_indicators = [
            'DFHCE',  # CICS message prefix
            'CICS',
            'TRANSACTION',
            'APPLID',
            'NETNAME',
            'CLEAR',
            'CESN',  # Sign-on transaction
            'CESF',  # Sign-off transaction
            'CEMT',  # Master terminal transaction
            'CEDA',  # Resource definition
            'CEDF'   # Execution diagnostic facility
        ]
        
        return any(indicator in screen_text.upper() for indicator in cics_indicators)
    
    def parse_cics_message(self, screen_text):
        """Parse CICS system messages"""
        messages = []
        
        for line in screen_text.split('\n'):
            # CICS messages start with DFH
            if 'DFH' in line:
                msg_match = re.search(r'(DFH\w+\d+\w*)\s+(.*)', line)
                if msg_match:
                    messages.append({
                        'code': msg_match.group(1),
                        'text': msg_match.group(2).strip()
                    })
        
        return messages
    
    def extract_transaction_id(self, screen_text):
        """Extract CICS transaction ID from screen"""
        # Look for 4-character transaction codes
        lines = screen_text.split('\n')
        
        for line in lines[:5]:  # Check first few lines
            words = line.split()
            for word in words:
                if len(word) == 4 and word.isupper():
                    return word
        
        return None
    
    def parse_cemt_output(self, screen_text):
        """Parse CEMT (Master Terminal) command output"""
        resources = []
        
        lines = screen_text.split('\n')
        
        for line in lines:
            # CEMT INQUIRE output format
            if any(keyword in line.upper() for keyword in ['TRANSACTION', 'PROGRAM', 'FILE', 'TASK']):
                resource = {
                    'type': None,
                    'name': None,
                    'status': None,
                    'attributes': []
                }
                
                if 'TRANSACTION' in line.upper():
                    resource['type'] = 'TRANSACTION'
                    trans_match = re.search(r'TRANSACTION\((\w+)\)', line)
                    if trans_match:
                        resource['name'] = trans_match.group(1)
                
                elif 'PROGRAM' in line.upper():
                    resource['type'] = 'PROGRAM'
                    prog_match = re.search(r'PROGRAM\((\w+)\)', line)
                    if prog_match:
                        resource['name'] = prog_match.group(1)
                
                elif 'FILE' in line.upper():
                    resource['type'] = 'FILE'
                    file_match = re.search(r'FILE\((\w+)\)', line)
                    if file_match:
                        resource['name'] = file_match.group(1)
                
                # Status
                if 'ENABLED' in line.upper():
                    resource['status'] = 'ENABLED'
                elif 'DISABLED' in line.upper():
                    resource['status'] = 'DISABLED'
                
                # Attributes
                for attr in ['OPEN', 'CLOSED', 'INSERVICE', 'OUTSERVICE']:
                    if attr in line.upper():
                        resource['attributes'].append(attr)
                
                if resource['name']:
                    resources.append(resource)
        
        return resources
    
    def parse_cedf_screen(self, screen_text):
        """Parse CEDF (Execution Diagnostic Facility) screen"""
        debug_info = {
            'transaction': None,
            'program': None,
            'command': None,
            'response': None,
            'eib_fields': {}
        }
        
        for line in screen_text.split('\n'):
            if 'TRANSACTION' in line.upper():
                trans_match = re.search(r'TRANSACTION\s+(\w+)', line)
                if trans_match:
                    debug_info['transaction'] = trans_match.group(1)
            
            if 'PROGRAM' in line.upper():
                prog_match = re.search(r'PROGRAM\s+(\w+)', line)
                if prog_match:
                    debug_info['program'] = prog_match.group(1)
            
            if 'EXEC CICS' in line.upper():
                debug_info['command'] = line.strip()
            
            if 'RESPONSE' in line.upper():
                resp_match = re.search(r'RESPONSE\((\w+)\)', line)
                if resp_match:
                    debug_info['response'] = resp_match.group(1)
            
            # EIB fields
            eib_match = re.search(r'EIB(\w+)\s*=\s*([^\s]+)', line)
            if eib_match:
                debug_info['eib_fields'][eib_match.group(1)] = eib_match.group(2)
        
        return debug_info
    
    def suggest_cics_commands(self, context):
        """Suggest CICS commands based on context"""
        suggestions = []
        
        # Sign-on/off
        suggestions.extend([
            'CESN - Sign on to CICS',
            'CESF - Sign off from CICS'
        ])
        
        # Master terminal
        suggestions.extend([
            'CEMT INQUIRE TRANSACTION(ALL)',
            'CEMT INQUIRE PROGRAM(ALL)',
            'CEMT INQUIRE TASK',
            'CEMT INQUIRE SYSTEM'
        ])
        
        # Resource definition
        suggestions.extend([
            'CEDA DISPLAY TRANSACTION(name)',
            'CEDA DISPLAY PROGRAM(name)',
            'CEDA DISPLAY GROUP(name)'
        ])
        
        # Debugging
        suggestions.extend([
            'CEDF - Enable execution diagnostics',
            'CEBR - Browse temporary storage'
        ])
        
        return suggestions
    
    def check_cics_error(self, screen_text):
        """Check for CICS errors"""
        error_codes = [
            'NOTAUTH',  # Not authorized
            'INVREQ',   # Invalid request
            'NOTFND',   # Not found
            'DISABLED', # Resource disabled
            'PGMIDERR', # Program not found
            'TRANSIDERR', # Transaction not found
            'FILENOTFOUND'
        ]
        
        errors = []
        for code in error_codes:
            if code in screen_text.upper():
                errors.append(code)
        
        return errors
    
    def parse_sign_on_screen(self, screen_text):
        """Parse CICS sign-on screen (CESN)"""
        sign_on = {
            'userid_field': None,
            'password_field': None,
            'language_field': None,
            'applid': None
        }
        
        # Look for common field labels
        for line in screen_text.split('\n'):
            if 'USERID' in line.upper() or 'USER ID' in line.upper():
                sign_on['userid_field'] = line.strip()
            if 'PASSWORD' in line.upper():
                sign_on['password_field'] = line.strip()
            if 'LANGUAGE' in line.upper():
                sign_on['language_field'] = line.strip()
            if 'APPLID' in line.upper():
                applid_match = re.search(r'APPLID[:\s]+(\w+)', line)
                if applid_match:
                    sign_on['applid'] = applid_match.group(1)
        
        return sign_on
