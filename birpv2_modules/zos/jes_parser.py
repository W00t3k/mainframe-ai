#!/usr/bin/env python3
"""
JES (Job Entry Subsystem) Parser for z/OS
Handles JES2/JES3 output parsing and job submission
"""

import re
from datetime import datetime

class JESParser:
    """Parser for JES output and job management"""
    
    def __init__(self):
        self.job_pattern = re.compile(r'(\w+)\s+(\w+)\s+(\w+)\s+(\d+)\s+(\w+)\s+(\d+)')
        self.jobid_pattern = re.compile(r'JOB\d{5}')
        
    def parse_job_list(self, screen_text):
        """
        Parse JES job list output
        Returns list of job dictionaries
        """
        jobs = []
        lines = screen_text.split('\n')
        
        for line in lines:
            # Look for job entries
            match = self.job_pattern.search(line)
            if match:
                job = {
                    'jobname': match.group(1),
                    'jobid': match.group(2),
                    'owner': match.group(3),
                    'status': match.group(4),
                    'class': match.group(5),
                    'return_code': match.group(6) if len(match.groups()) > 5 else None
                }
                jobs.append(job)
        
        return jobs
    
    def find_jobid(self, screen_text):
        """Extract JOB ID from screen"""
        match = self.jobid_pattern.search(screen_text)
        return match.group(0) if match else None
    
    def parse_job_output(self, screen_text):
        """
        Parse JES job output (SDSF/SPOOL)
        Returns structured job output
        """
        output = {
            'jobname': None,
            'jobid': None,
            'steps': [],
            'messages': [],
            'return_code': None
        }
        
        lines = screen_text.split('\n')
        current_step = None
        
        for line in lines:
            # Job header
            if 'JOB' in line and 'STARTED' in line:
                parts = line.split()
                if len(parts) >= 2:
                    output['jobname'] = parts[0]
                    output['jobid'] = parts[1]
            
            # Step execution
            if 'IEF142I' in line or 'IEF404I' in line:
                step_match = re.search(r'(\w+)\s+STEP\s+(\w+)', line)
                if step_match:
                    current_step = {
                        'name': step_match.group(2),
                        'program': None,
                        'return_code': None
                    }
                    output['steps'].append(current_step)
            
            # Return codes
            if 'COND CODE' in line or 'COMPLETION CODE' in line:
                rc_match = re.search(r'(\d{4})', line)
                if rc_match:
                    rc = rc_match.group(1)
                    if current_step:
                        current_step['return_code'] = rc
                    output['return_code'] = rc
            
            # Messages
            if any(msg in line for msg in ['IEF', 'IEC', 'IGD', 'ICH']):
                output['messages'].append(line.strip())
        
        return output
    
    def create_jcl(self, jobname, stepname, program, params=None):
        """
        Generate basic JCL for job submission
        """
        jcl = f"""//{ jobname} JOB (ACCT),'BIRP',CLASS=A,MSGCLASS=H,
//         MSGLEVEL=(1,1),NOTIFY=&SYSUID
//*
//{stepname} EXEC PGM={program}"""
        
        if params:
            jcl += f",PARM='{params}'"
        
        jcl += """
//STEPLIB  DD DSN=SYS1.LINKLIB,DISP=SHR
//SYSPRINT DD SYSOUT=*
//SYSOUT   DD SYSOUT=*
//"""
        
        return jcl
    
    def parse_allocation_messages(self, screen_text):
        """Parse dataset allocation messages"""
        allocations = []
        
        for line in screen_text.split('\n'):
            if 'IEF285I' in line:  # Dataset allocated
                match = re.search(r'(\w+\.\w+(?:\.\w+)*)', line)
                if match:
                    allocations.append({
                        'type': 'allocated',
                        'dataset': match.group(1)
                    })
            elif 'IEF287I' in line:  # Dataset kept
                match = re.search(r'(\w+\.\w+(?:\.\w+)*)', line)
                if match:
                    allocations.append({
                        'type': 'kept',
                        'dataset': match.group(1)
                    })
        
        return allocations
    
    def detect_jes_screen(self, screen_text):
        """Detect if current screen is JES-related"""
        jes_indicators = [
            'SDSF',
            'JOB QUEUE',
            'OUTPUT QUEUE',
            'STATUS DISPLAY',
            'JES2',
            'JES3'
        ]
        
        return any(indicator in screen_text.upper() for indicator in jes_indicators)
    
    def extract_spool_info(self, screen_text):
        """Extract SPOOL file information"""
        spool_files = []
        
        for line in screen_text.split('\n'):
            # SDSF output format
            if re.match(r'\s*\d+\s+\w+', line):
                parts = line.split()
                if len(parts) >= 4:
                    spool_files.append({
                        'id': parts[0],
                        'ddname': parts[1],
                        'stepname': parts[2],
                        'records': parts[3] if len(parts) > 3 else None
                    })
        
        return spool_files
