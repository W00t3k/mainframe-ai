#!/usr/bin/env python3
"""
TSO (Time Sharing Option) Helper for z/OS
Interactive command processing and dataset utilities
"""

import re

class TSOHelper:
    """Helper for TSO operations"""
    
    def __init__(self):
        self.dataset_pattern = re.compile(r"[A-Z0-9#@$]{1,8}(?:\.[A-Z0-9#@$]{1,8}){0,21}")
        
    def detect_tso_screen(self, screen_text):
        """Detect if current screen is TSO"""
        tso_indicators = [
            'READY',
            'TSO',
            'ISPF',
            'OPTION ===>',
            'COMMAND ===>',
            'EDIT',
            'BROWSE',
            'UTILITIES',
            'DSLIST'
        ]
        
        return any(indicator in screen_text.upper() for indicator in tso_indicators)
    
    def detect_ispf_panel(self, screen_text):
        """Detect ISPF panel type"""
        panels = {
            'PRIMARY': 'ISPF PRIMARY OPTION MENU',
            'DSLIST': 'DSLIST',
            'EDIT': 'EDIT',
            'BROWSE': 'BROWSE',
            'UTILITIES': 'UTILITY',
            'DATASET': 'DATA SET',
            'MEMBER': 'MEMBER',
            'ALLOCATE': 'ALLOCATE'
        }
        
        for panel_type, indicator in panels.items():
            if indicator in screen_text.upper():
                return panel_type
        
        return 'UNKNOWN'
    
    def parse_dataset_list(self, screen_text):
        """Parse TSO dataset list (DSLIST)"""
        datasets = []
        
        lines = screen_text.split('\n')
        
        for line in lines:
            # Look for dataset names
            ds_match = self.dataset_pattern.search(line)
            if ds_match:
                dsname = ds_match.group(0)
                
                # Extract additional info if available
                dataset = {
                    'name': dsname,
                    'volume': None,
                    'device': None,
                    'dsorg': None,
                    'recfm': None,
                    'lrecl': None
                }
                
                # Volume
                vol_match = re.search(r'(\w{6})\s+', line)
                if vol_match:
                    dataset['volume'] = vol_match.group(1)
                
                # DSORG
                if 'PO' in line:
                    dataset['dsorg'] = 'PO'
                elif 'PS' in line:
                    dataset['dsorg'] = 'PS'
                elif 'VS' in line:
                    dataset['dsorg'] = 'VS'
                
                # RECFM
                recfm_match = re.search(r'(FB|VB|F|V|U)\s', line)
                if recfm_match:
                    dataset['recfm'] = recfm_match.group(1)
                
                # LRECL
                lrecl_match = re.search(r'(\d{1,5})\s', line)
                if lrecl_match:
                    dataset['lrecl'] = lrecl_match.group(1)
                
                datasets.append(dataset)
        
        return datasets
    
    def parse_member_list(self, screen_text):
        """Parse PDS member list"""
        members = []
        
        lines = screen_text.split('\n')
        
        for line in lines:
            # Member names are typically 8 characters or less
            member_match = re.match(r'\s*([A-Z0-9#@$]{1,8})\s+', line)
            if member_match:
                member = {
                    'name': member_match.group(1),
                    'version': None,
                    'created': None,
                    'changed': None,
                    'size': None,
                    'id': None
                }
                
                # Version
                ver_match = re.search(r'(\d+\.\d+)', line)
                if ver_match:
                    member['version'] = ver_match.group(1)
                
                # Dates
                date_matches = re.findall(r'(\d{2}/\d{2}/\d{2})', line)
                if len(date_matches) >= 1:
                    member['created'] = date_matches[0]
                if len(date_matches) >= 2:
                    member['changed'] = date_matches[1]
                
                # Size
                size_match = re.search(r'(\d+)\s+\d+\s+\d+', line)
                if size_match:
                    member['size'] = size_match.group(1)
                
                # User ID
                id_match = re.search(r'([A-Z0-9]{1,8})\s*$', line)
                if id_match:
                    member['id'] = id_match.group(1)
                
                members.append(member)
        
        return members
    
    def parse_tso_messages(self, screen_text):
        """Parse TSO system messages"""
        messages = []
        
        for line in screen_text.split('\n'):
            # TSO messages typically start with IKJ, IEF, or other prefixes
            if re.match(r'[A-Z]{3}\d{3,4}[A-Z]', line):
                messages.append(line.strip())
        
        return messages
    
    def extract_command_result(self, screen_text):
        """Extract TSO command result"""
        result = {
            'command': None,
            'output': [],
            'return_code': None
        }
        
        lines = screen_text.split('\n')
        
        for i, line in enumerate(lines):
            # Command line
            if 'READY' in line and i > 0:
                result['command'] = lines[i-1].strip()
            
            # Output lines
            if not line.strip().startswith('***') and line.strip():
                result['output'].append(line)
            
            # Return code
            rc_match = re.search(r'RETURN CODE\s*=\s*(\d+)', line)
            if rc_match:
                result['return_code'] = int(rc_match.group(1))
        
        return result
    
    def suggest_tso_commands(self, context):
        """Suggest TSO commands based on context"""
        suggestions = []
        
        # Dataset commands
        suggestions.extend([
            'LISTDS dsname - List dataset information',
            'LISTCAT - List catalog entries',
            'DELETE dsname - Delete dataset',
            'RENAME oldname newname - Rename dataset'
        ])
        
        # File commands
        suggestions.extend([
            'ALLOC - Allocate dataset',
            'FREE - Free dataset',
            'ATTRIB - Display attributes'
        ])
        
        # ISPF commands
        suggestions.extend([
            'ISPF - Start ISPF',
            'TSO - Return to TSO',
            '=3.4 - Dataset list utility',
            '=2 - Edit',
            '=1 - Browse'
        ])
        
        # System commands
        suggestions.extend([
            'TIME - Display time',
            'STATUS - Display session status',
            'LOGOFF - End session'
        ])
        
        return suggestions
    
    def parse_allocation_screen(self, screen_text):
        """Parse dataset allocation screen"""
        alloc = {
            'dsname': None,
            'volume': None,
            'unit': None,
            'space': None,
            'dsorg': None,
            'recfm': None,
            'lrecl': None,
            'blksize': None
        }
        
        for line in screen_text.split('\n'):
            if 'DATA SET NAME' in line.upper():
                ds_match = self.dataset_pattern.search(line)
                if ds_match:
                    alloc['dsname'] = ds_match.group(0)
            
            if 'VOLUME' in line.upper():
                vol_match = re.search(r'VOLUME[:\s]+(\w+)', line)
                if vol_match:
                    alloc['volume'] = vol_match.group(1)
            
            if 'SPACE UNITS' in line.upper():
                space_match = re.search(r'(TRACKS|CYLINDERS|BLOCKS)', line.upper())
                if space_match:
                    alloc['space'] = space_match.group(1)
            
            if 'RECORD FORMAT' in line.upper():
                recfm_match = re.search(r'(FB|VB|F|V|U)', line)
                if recfm_match:
                    alloc['recfm'] = recfm_match.group(1)
            
            if 'RECORD LENGTH' in line.upper():
                lrecl_match = re.search(r'(\d+)', line)
                if lrecl_match:
                    alloc['lrecl'] = lrecl_match.group(1)
        
        return alloc
    
    def check_dataset_exists(self, screen_text):
        """Check if dataset exists based on screen output"""
        not_found_indicators = [
            'NOT IN CATALOG',
            'NOT FOUND',
            'DATASET NOT FOUND',
            'NOT CATALOGED'
        ]
        
        return not any(indicator in screen_text.upper() for indicator in not_found_indicators)
