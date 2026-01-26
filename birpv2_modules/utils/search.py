"""Search utilities for BIRP"""
import re

def find_first(history, text):
    """Find first occurrence of text in history"""
    transid = 0
    for trans in history:
        row = 0
        # Check request
        for line in trans.request.stringbuffer:
            col = line.find(text)
            if col >= 0:
                return (transid, 0, row, col)
            row += 1
        row = 0
        # Check response
        for line in trans.response.stringbuffer:
            col = line.find(text)
            if col >= 0:
                return (transid, 1, row, col)
            row += 1
        transid += 1
    return (-1, -1, -1, -1)

def find_all(history, text, case_sensitive=True, use_regex=False):
    """
    Search transaction history for text or regex pattern
    
    Args:
        history: History object to search
        text: Text or regex pattern to search for
        case_sensitive: Whether search should be case sensitive
        use_regex: Whether to use regex matching
        
    Returns:
        list: List of tuples (transid, request/response, row, col)
    """
    result = []
    
    # Compile regex if needed
    if use_regex:
        try:
            pattern = re.compile(text, 0 if case_sensitive else re.IGNORECASE)
        except re.error as e:
            print(f'Invalid regex pattern: {e}')
            return result
    else:
        search_text = text if case_sensitive else text.lower()
    
    for transid, trans in enumerate(history):
        # Check request
        for row, line in enumerate(trans.request.stringbuffer):
            if use_regex:
                match = pattern.search(line)
                if match:
                    result.append((transid, 0, row, match.start()))
            else:
                compare_line = line if case_sensitive else line.lower()
                col = compare_line.find(search_text)
                if col >= 0:
                    result.append((transid, 0, row, col))
        
        # Check response
        for row, line in enumerate(trans.response.stringbuffer):
            if use_regex:
                match = pattern.search(line)
                if match:
                    result.append((transid, 1, row, match.start()))
            else:
                compare_line = line if case_sensitive else line.lower()
                col = compare_line.find(search_text)
                if col >= 0:
                    result.append((transid, 1, row, col))
    
    return result
