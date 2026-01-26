#!/usr/bin/env python3
"""
Automated Security Scanner for BIRP v2
Performs automated screen scraping, credential detection, and vulnerability scanning
"""

import re
from datetime import datetime
from ..core.models import Screen, Transaction
from ..utils.logger import log_info, log_warning, log_error


class SecurityScanner:
    """Automated security scanner for mainframe applications"""
    
    def __init__(self, emulator, history):
        self.emulator = emulator
        self.history = history
        self.findings = []
        
        # Patterns for sensitive data detection
        self.patterns = {
            'password': [
                r'password\s*[:=]?\s*([^\s]+)',
                r'passwd\s*[:=]?\s*([^\s]+)',
                r'pwd\s*[:=]?\s*([^\s]+)',
            ],
            'userid': [
                r'userid\s*[:=]?\s*([^\s]+)',
                r'user\s*id\s*[:=]?\s*([^\s]+)',
                r'username\s*[:=]?\s*([^\s]+)',
            ],
            'ssn': [
                r'\b\d{3}-\d{2}-\d{4}\b',
                r'\b\d{9}\b',
            ],
            'credit_card': [
                r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
            ],
            'api_key': [
                r'api[_-]?key\s*[:=]?\s*([^\s]+)',
                r'token\s*[:=]?\s*([^\s]+)',
            ],
        }
    
    def scan_screen(self, screen):
        """Scan a single screen for security issues"""
        findings = []
        
        # Check for hidden fields with sensitive data
        for field in screen.hidden_fields:
            if field.contents.strip():
                findings.append({
                    'type': 'hidden_field',
                    'severity': 'high',
                    'location': f'[{field.row},{field.col}]',
                    'content': field.contents,
                    'message': 'Hidden field contains data'
                })
        
        # Check for unprotected sensitive fields
        for field in screen.input_fields:
            field_text = field.contents.lower()
            if any(keyword in field_text for keyword in ['password', 'passwd', 'pwd']):
                if not field.hidden:
                    findings.append({
                        'type': 'unprotected_password',
                        'severity': 'critical',
                        'location': f'[{field.row},{field.col}]',
                        'message': 'Password field is not hidden'
                    })
        
        # Scan all text for sensitive patterns
        screen_text = str(screen)
        for data_type, patterns in self.patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, screen_text, re.IGNORECASE)
                for match in matches:
                    findings.append({
                        'type': f'sensitive_data_{data_type}',
                        'severity': 'high',
                        'content': match.group(0),
                        'message': f'Potential {data_type} detected in screen'
                    })
        
        return findings
    
    def scan_history(self):
        """Scan entire transaction history for security issues"""
        log_info('Starting security scan of transaction history...')
        all_findings = []
        
        for idx, trans in enumerate(self.history):
            # Scan request screen
            request_findings = self.scan_screen(trans.request)
            for finding in request_findings:
                finding['transaction'] = idx
                finding['screen_type'] = 'request'
                all_findings.append(finding)
            
            # Scan response screen
            response_findings = self.scan_screen(trans.response)
            for finding in response_findings:
                finding['transaction'] = idx
                finding['screen_type'] = 'response'
                all_findings.append(finding)
        
        self.findings = all_findings
        log_info(f'Security scan complete: {len(all_findings)} findings')
        return all_findings
    
    def detect_credentials(self):
        """Extract potential credentials from history"""
        credentials = []
        
        for idx, trans in enumerate(self.history):
            # Look for modified fields (user input)
            for field in trans.data:
                field_text = field.contents.lower()
                
                # Check if this looks like a userid field
                if any(keyword in field_text for keyword in ['userid', 'user', 'logon']):
                    credentials.append({
                        'type': 'userid',
                        'value': field.contents,
                        'transaction': idx,
                        'location': f'[{field.row},{field.col}]'
                    })
                
                # Check if this looks like a password field
                if any(keyword in field_text for keyword in ['password', 'passwd', 'pwd']):
                    credentials.append({
                        'type': 'password',
                        'value': field.contents,
                        'transaction': idx,
                        'location': f'[{field.row},{field.col}]',
                        'hidden': field.hidden
                    })
        
        log_info(f'Detected {len(credentials)} potential credentials')
        return credentials
    
    def check_access_control(self):
        """Check for access control issues"""
        issues = []
        
        for idx, trans in enumerate(self.history):
            screen_text = str(trans.response).lower()
            
            # Check for error messages indicating access issues
            if any(msg in screen_text for msg in ['not authorized', 'access denied', 'permission denied']):
                issues.append({
                    'type': 'access_denied',
                    'transaction': idx,
                    'message': 'Access control restriction detected'
                })
            
            # Check for successful privilege escalation indicators
            if any(msg in screen_text for msg in ['special', 'operations', 'admin', 'system']):
                issues.append({
                    'type': 'privilege_indicator',
                    'transaction': idx,
                    'message': 'Potential privileged access detected'
                })
        
        return issues
    
    def generate_report(self):
        """Generate comprehensive security report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'transactions_analyzed': len(self.history),
            'findings': self.findings,
            'credentials': self.detect_credentials(),
            'access_control': self.check_access_control(),
            'summary': {
                'critical': len([f for f in self.findings if f.get('severity') == 'critical']),
                'high': len([f for f in self.findings if f.get('severity') == 'high']),
                'medium': len([f for f in self.findings if f.get('severity') == 'medium']),
                'low': len([f for f in self.findings if f.get('severity') == 'low']),
            }
        }
        
        return report


class AutomatedCrawler:
    """Automated screen crawler for mainframe applications"""
    
    def __init__(self, emulator, history):
        self.emulator = emulator
        self.history = history
        self.visited_screens = set()
        self.screen_map = {}
    
    def get_screen_hash(self, screen):
        """Generate hash of screen for deduplication"""
        return hash(str(screen))
    
    def crawl_menu(self, max_depth=3, current_depth=0):
        """Automatically crawl through menu options"""
        if current_depth >= max_depth:
            return
        
        # Read current screen
        buffer = self.emulator.exec_command_with_timeout(b'ReadBuffer(Ascii)', timeout=5).data
        if buffer and isinstance(buffer[0], bytes):
            buffer = [line.decode('utf-8') if isinstance(line, bytes) else line for line in buffer]
        screen = Screen(buffer)
        
        screen_hash = self.get_screen_hash(screen)
        
        # Skip if already visited
        if screen_hash in self.visited_screens:
            return
        
        self.visited_screens.add(screen_hash)
        self.screen_map[screen_hash] = {
            'depth': current_depth,
            'screen': screen,
            'timestamp': datetime.now()
        }
        
        log_info(f'Crawling depth {current_depth}, visited {len(self.visited_screens)} screens')
        
        # Look for menu options (numbers 1-9, letters A-Z)
        screen_text = str(screen)
        
        # Try numeric options
        for option in range(1, 10):
            try:
                self.emulator.send_string(str(option))
                self.emulator.send_enter()
                self.emulator.exec_command_with_timeout(b'Wait(1,3270Mode)', timeout=10)
                
                # Recursively crawl
                self.crawl_menu(max_depth, current_depth + 1)
                
                # Go back (usually PF3)
                self.emulator.exec_command_with_timeout(b'PF(3)', timeout=5)
                self.emulator.exec_command_with_timeout(b'Wait(1,3270Mode)', timeout=10)
                
            except Exception as e:
                log_error(f'Error crawling option {option}: {e}')
                continue
    
    def map_application(self):
        """Create a map of the application structure"""
        log_info('Starting application mapping...')
        self.crawl_menu()
        
        return {
            'total_screens': len(self.visited_screens),
            'screen_map': self.screen_map,
            'timestamp': datetime.now().isoformat()
        }


class FieldFuzzer:
    """Fuzzer for testing input field validation"""
    
    def __init__(self, emulator):
        self.emulator = emulator
        self.results = []
        
        # Fuzzing payloads
        self.payloads = {
            'overflow': ['A' * i for i in [100, 500, 1000, 5000]],
            'special_chars': ['!@#$%^&*()', '<>?:"{}|', '`~[]\\;\',./', '../../etc/passwd'],
            'sql_injection': ["' OR '1'='1", "'; DROP TABLE users--", "1' UNION SELECT NULL--"],
            'command_injection': ['; ls -la', '| cat /etc/passwd', '`whoami`'],
            'format_string': ['%s%s%s%s', '%x%x%x%x', '%n%n%n%n'],
            'null_bytes': ['\x00', 'test\x00test', '\x00\x00\x00'],
            'unicode': ['\\u0000', '\\uffff', '\\u202e'],
        }
    
    def fuzz_field(self, row, col, payloads):
        """Fuzz a specific field with payloads"""
        results = []
        
        for payload_type, payload_list in payloads.items():
            for payload in payload_list:
                try:
                    # Move to field
                    self.emulator.move_to(row, col)
                    self.emulator.delete_field()
                    
                    # Send payload
                    self.emulator.send_string(payload)
                    self.emulator.send_enter()
                    self.emulator.exec_command_with_timeout(b'Wait(1,3270Mode)', timeout=10)
                    
                    # Read response
                    buffer = self.emulator.exec_command_with_timeout(b'ReadBuffer(Ascii)', timeout=5).data
                    if buffer and isinstance(buffer[0], bytes):
                        buffer = [line.decode('utf-8') if isinstance(line, bytes) else line for line in buffer]
                    response = Screen(buffer)
                    
                    # Check for interesting responses
                    response_text = str(response).lower()
                    
                    result = {
                        'field': f'[{row},{col}]',
                        'payload_type': payload_type,
                        'payload': payload,
                        'response_length': len(response_text),
                        'errors': []
                    }
                    
                    # Look for error indicators
                    if 'error' in response_text:
                        result['errors'].append('Error message detected')
                    if 'invalid' in response_text:
                        result['errors'].append('Invalid input message')
                    if 'exception' in response_text:
                        result['errors'].append('Exception detected')
                    
                    results.append(result)
                    
                except Exception as e:
                    log_error(f'Fuzzing error: {e}')
                    continue
        
        return results
    
    def fuzz_screen(self, screen):
        """Fuzz all input fields on a screen"""
        log_info(f'Fuzzing {len(screen.input_fields)} input fields...')
        
        for field in screen.input_fields:
            field_results = self.fuzz_field(field.row, field.col, self.payloads)
            self.results.extend(field_results)
        
        return self.results
