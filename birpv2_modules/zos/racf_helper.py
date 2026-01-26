#!/usr/bin/env python3
"""
RACF (Resource Access Control Facility) Helper for z/OS
Security and access control utilities
"""

import re

class RACFHelper:
    """Helper for RACF security operations"""
    
    def __init__(self):
        self.user_pattern = re.compile(r'USER=(\w+)')
        self.group_pattern = re.compile(r'GROUP=(\w+)')
        
    def parse_listuser_output(self, screen_text):
        """
        Parse RACF LISTUSER command output
        Returns user profile information
        """
        profile = {
            'userid': None,
            'name': None,
            'default_group': None,
            'groups': [],
            'attributes': [],
            'last_access': None,
            'password_date': None,
            'revoked': False,
            'special': False,
            'operations': False,
            'auditor': False
        }
        
        lines = screen_text.split('\n')
        
        for line in lines:
            line_upper = line.upper()
            
            # User ID
            if 'USER=' in line_upper:
                match = self.user_pattern.search(line)
                if match:
                    profile['userid'] = match.group(1)
            
            # Name
            if 'NAME=' in line_upper:
                name_match = re.search(r'NAME=([^=]+?)(?:\s+\w+=|$)', line)
                if name_match:
                    profile['name'] = name_match.group(1).strip()
            
            # Default group
            if 'DEFAULT-GROUP=' in line_upper:
                match = self.group_pattern.search(line)
                if match:
                    profile['default_group'] = match.group(1)
            
            # Groups
            if 'GROUP=' in line_upper and 'DEFAULT-GROUP' not in line_upper:
                groups = re.findall(r'GROUP=(\w+)', line)
                profile['groups'].extend(groups)
            
            # Attributes
            if 'SPECIAL' in line_upper:
                profile['special'] = True
                profile['attributes'].append('SPECIAL')
            if 'OPERATIONS' in line_upper:
                profile['operations'] = True
                profile['attributes'].append('OPERATIONS')
            if 'AUDITOR' in line_upper:
                profile['auditor'] = True
                profile['attributes'].append('AUDITOR')
            if 'REVOKED' in line_upper:
                profile['revoked'] = True
                profile['attributes'].append('REVOKED')
            
            # Last access
            if 'LAST-ACCESS=' in line_upper:
                date_match = re.search(r'LAST-ACCESS=(\d{2}/\d{2}/\d{2})', line)
                if date_match:
                    profile['last_access'] = date_match.group(1)
            
            # Password date
            if 'PASSDATE=' in line_upper:
                date_match = re.search(r'PASSDATE=(\d{2}/\d{2}/\d{2})', line)
                if date_match:
                    profile['password_date'] = date_match.group(1)
        
        return profile
    
    def parse_listgrp_output(self, screen_text):
        """Parse RACF LISTGRP command output"""
        group = {
            'groupid': None,
            'owner': None,
            'superior_group': None,
            'members': [],
            'subgroups': []
        }
        
        for line in screen_text.split('\n'):
            if 'GROUP=' in line.upper():
                match = self.group_pattern.search(line)
                if match:
                    group['groupid'] = match.group(1)
            
            if 'OWNER=' in line.upper():
                owner_match = re.search(r'OWNER=(\w+)', line)
                if owner_match:
                    group['owner'] = owner_match.group(1)
            
            if 'SUPGRP=' in line.upper():
                sup_match = re.search(r'SUPGRP=(\w+)', line)
                if sup_match:
                    group['superior_group'] = sup_match.group(1)
            
            if 'USER=' in line.upper():
                users = re.findall(r'USER=(\w+)', line)
                group['members'].extend(users)
        
        return group
    
    def parse_listdsd_output(self, screen_text):
        """Parse RACF LISTDSD (dataset) command output"""
        dataset = {
            'name': None,
            'owner': None,
            'universal_access': None,
            'access_list': []
        }
        
        for line in screen_text.split('\n'):
            if 'DATASET=' in line.upper():
                ds_match = re.search(r'DATASET=([^\s]+)', line)
                if ds_match:
                    dataset['name'] = ds_match.group(1)
            
            if 'OWNER=' in line.upper():
                owner_match = re.search(r'OWNER=(\w+)', line)
                if owner_match:
                    dataset['owner'] = owner_match.group(1)
            
            if 'UACC=' in line.upper():
                uacc_match = re.search(r'UACC=(\w+)', line)
                if uacc_match:
                    dataset['universal_access'] = uacc_match.group(1)
            
            # Access list entries
            access_match = re.search(r'ID\((\w+)\)\s+ACCESS\((\w+)\)', line)
            if access_match:
                dataset['access_list'].append({
                    'id': access_match.group(1),
                    'access': access_match.group(2)
                })
        
        return dataset
    
    def detect_racf_screen(self, screen_text):
        """Detect if current screen is RACF-related"""
        racf_indicators = [
            'RACF',
            'LISTUSER',
            'LISTGRP',
            'LISTDSD',
            'RLIST',
            'SEARCH',
            'ICH'  # RACF message prefix
        ]
        
        return any(indicator in screen_text.upper() for indicator in racf_indicators)
    
    def extract_racf_messages(self, screen_text):
        """Extract RACF messages from screen"""
        messages = []
        
        for line in screen_text.split('\n'):
            if line.strip().startswith('ICH'):
                messages.append(line.strip())
        
        return messages
    
    def check_access_denied(self, screen_text):
        """Check if screen shows access denied"""
        denied_indicators = [
            'ICH408I',  # Not authorized
            'ICH420I',  # Not authorized to resource
            'INSUFFICIENT ACCESS',
            'NOT AUTHORIZED',
            'ACCESS DENIED'
        ]
        
        return any(indicator in screen_text.upper() for indicator in denied_indicators)
    
    def suggest_racf_commands(self, context):
        """Suggest RACF commands based on context"""
        suggestions = []
        
        if 'user' in context.lower():
            suggestions.extend([
                'LISTUSER userid',
                'LISTUSER userid NORACF',
                'SEARCH CLASS(USER) MASK(pattern*)'
            ])
        
        if 'group' in context.lower():
            suggestions.extend([
                'LISTGRP groupid',
                'SEARCH CLASS(GROUP) MASK(pattern*)'
            ])
        
        if 'dataset' in context.lower() or 'dsn' in context.lower():
            suggestions.extend([
                'LISTDSD DATASET(dsname) ALL',
                'SEARCH CLASS(DATASET) MASK(pattern*)'
            ])
        
        return suggestions
