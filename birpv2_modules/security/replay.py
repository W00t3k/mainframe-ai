#!/usr/bin/env python3
"""
Session Replay for BIRP v2
Replay recorded transactions for testing and automation
"""

from datetime import datetime
from ..core.models import Screen, Transaction
from ..utils.logger import log_info, log_warning, log_error


class SessionReplay:
    """Replay recorded TN3270 sessions"""
    
    def __init__(self, emulator, history):
        self.emulator = emulator
        self.history = history
        self.replay_log = []
    
    def replay_transaction(self, transaction, verify=True):
        """Replay a single transaction"""
        log_info(f'Replaying transaction with key: {transaction.key}')
        
        try:
            # Get current screen
            buffer = self.emulator.exec_command_with_timeout(b'ReadBuffer(Ascii)', timeout=5).data
            if buffer and isinstance(buffer[0], bytes):
                buffer = [line.decode('utf-8') if isinstance(line, bytes) else line for line in buffer]
            current_screen = Screen(buffer)
            
            # Fill in the fields from the original transaction
            for field in transaction.data:
                if field.contents.strip():
                    try:
                        self.emulator.move_to(field.row, field.col)
                        self.emulator.delete_field()
                        self.emulator.send_string(field.contents)
                    except Exception as e:
                        log_warning(f'Could not fill field at [{field.row},{field.col}]: {e}')
            
            # Send the key that was used
            if transaction.key == 'enter':
                self.emulator.send_enter()
            elif transaction.key.startswith('PF('):
                pf_num = transaction.key[3:-1]
                self.emulator.exec_command_with_timeout(f'PF({pf_num})', timeout=5.encode())
            elif transaction.key.startswith('PA('):
                pa_num = transaction.key[3:-1]
                self.emulator.exec_command_with_timeout(f'PA({pa_num})', timeout=5.encode())
            
            self.emulator.exec_command_with_timeout(b'Wait(1,3270Mode)', timeout=10)
            
            # Get response
            buffer = self.emulator.exec_command_with_timeout(b'ReadBuffer(Ascii)', timeout=5).data
            if buffer and isinstance(buffer[0], bytes):
                buffer = [line.decode('utf-8') if isinstance(line, bytes) else line for line in buffer]
            response_screen = Screen(buffer)
            
            # Verify if requested
            if verify:
                original_response = str(transaction.response)
                current_response = str(response_screen)
                
                if original_response == current_response:
                    log_info('Response matches original')
                    match = True
                else:
                    log_warning('Response differs from original')
                    match = False
            else:
                match = None
            
            result = {
                'timestamp': datetime.now().isoformat(),
                'key': transaction.key,
                'success': True,
                'match': match,
                'response': response_screen
            }
            
            self.replay_log.append(result)
            return result
            
        except Exception as e:
            log_error(f'Replay error: {e}')
            result = {
                'timestamp': datetime.now().isoformat(),
                'key': transaction.key,
                'success': False,
                'error': str(e)
            }
            self.replay_log.append(result)
            return result
    
    def replay_session(self, start_idx=0, end_idx=None, verify=True):
        """Replay multiple transactions"""
        if end_idx is None:
            end_idx = len(self.history)
        
        log_info(f'Replaying transactions {start_idx} to {end_idx}')
        
        results = []
        for idx in range(start_idx, end_idx):
            if idx >= len(self.history):
                break
            
            transaction = self.history[idx]
            result = self.replay_transaction(transaction, verify)
            results.append(result)
        
        return results
    
    def replay_with_modifications(self, transaction, field_modifications):
        """Replay a transaction with modified field values"""
        log_info('Replaying transaction with modifications')
        
        try:
            # Fill in fields with modifications
            for field in transaction.data:
                # Check if this field should be modified
                field_key = f'{field.row},{field.col}'
                if field_key in field_modifications:
                    new_value = field_modifications[field_key]
                    log_info(f'Modifying field [{field.row},{field.col}]: {field.contents} -> {new_value}')
                else:
                    new_value = field.contents
                
                if new_value.strip():
                    try:
                        self.emulator.move_to(field.row, field.col)
                        self.emulator.delete_field()
                        self.emulator.send_string(new_value)
                    except Exception as e:
                        log_warning(f'Could not fill field: {e}')
            
            # Send the key
            if transaction.key == 'enter':
                self.emulator.send_enter()
            elif transaction.key.startswith('PF('):
                pf_num = transaction.key[3:-1]
                self.emulator.exec_command_with_timeout(f'PF({pf_num})', timeout=5.encode())
            
            self.emulator.exec_command_with_timeout(b'Wait(1,3270Mode)', timeout=10)
            
            # Get response
            buffer = self.emulator.exec_command_with_timeout(b'ReadBuffer(Ascii)', timeout=5).data
            if buffer and isinstance(buffer[0], bytes):
                buffer = [line.decode('utf-8') if isinstance(line, bytes) else line for line in buffer]
            response_screen = Screen(buffer)
            
            return {
                'success': True,
                'response': response_screen,
                'modifications': field_modifications
            }
            
        except Exception as e:
            log_error(f'Modified replay error: {e}')
            return {
                'success': False,
                'error': str(e)
            }
    
    def automated_login(self, userid, password, userid_field=None, password_field=None):
        """Automated login with credentials"""
        log_info(f'Attempting automated login for user: {userid}')
        
        try:
            # Read current screen
            buffer = self.emulator.exec_command_with_timeout(b'ReadBuffer(Ascii)', timeout=5).data
            if buffer and isinstance(buffer[0], bytes):
                buffer = [line.decode('utf-8') if isinstance(line, bytes) else line for line in buffer]
            screen = Screen(buffer)
            
            # If field positions not provided, try to find them
            if userid_field is None or password_field is None:
                screen_text = str(screen).lower()
                
                # Look for userid field
                for field in screen.input_fields:
                    field_area = str(screen)[field.row * screen.cols:(field.row + 1) * screen.cols].lower()
                    if 'userid' in field_area or 'user id' in field_area:
                        userid_field = (field.row, field.col)
                        log_info(f'Found userid field at {userid_field}')
                    elif 'password' in field_area or 'passwd' in field_area:
                        password_field = (field.row, field.col)
                        log_info(f'Found password field at {password_field}')
            
            # Fill in credentials
            if userid_field:
                self.emulator.move_to(userid_field[0], userid_field[1])
                self.emulator.delete_field()
                self.emulator.send_string(userid)
            
            if password_field:
                self.emulator.move_to(password_field[0], password_field[1])
                self.emulator.delete_field()
                self.emulator.send_string(password)
            
            # Submit
            self.emulator.send_enter()
            self.emulator.exec_command_with_timeout(b'Wait(1,3270Mode)', timeout=10)
            
            # Check result
            buffer = self.emulator.exec_command_with_timeout(b'ReadBuffer(Ascii)', timeout=5).data
            if buffer and isinstance(buffer[0], bytes):
                buffer = [line.decode('utf-8') if isinstance(line, bytes) else line for line in buffer]
            response = Screen(buffer)
            response_text = str(response).lower()
            
            # Check for success indicators
            if 'invalid' in response_text or 'incorrect' in response_text or 'denied' in response_text:
                log_warning('Login appears to have failed')
                success = False
            else:
                log_info('Login appears successful')
                success = True
            
            return {
                'success': success,
                'userid': userid,
                'response': response
            }
            
        except Exception as e:
            log_error(f'Automated login error: {e}')
            return {
                'success': False,
                'error': str(e)
            }
    
    def brute_force_login(self, userids, passwords, delay=1):
        """Attempt multiple login combinations"""
        log_info(f'Starting brute force with {len(userids)} userids and {len(passwords)} passwords')
        
        results = []
        for userid in userids:
            for password in passwords:
                result = self.automated_login(userid, password)
                results.append(result)
                
                if result.get('success'):
                    log_info(f'Successful login: {userid}/{password}')
                    return results  # Stop on first success
                
                # Delay between attempts
                if delay > 0:
                    import time
                    time.sleep(delay)
        
        log_info('Brute force complete, no successful logins')
        return results
