"""Helper utilities for BIRP"""

def compare_screen(screen1, screen2, exact=False):
    """Compare two screens, allow fuzzy match"""
    diffcount = 0
    for linecount, line in enumerate(screen1.rawbuffer):
        if screen1.rawbuffer[linecount] != screen2.rawbuffer[linecount]:
            diffcount += 1
            if exact or diffcount > 2:
                return False
    return True

def screentofile(screen, filepath):
    """Save screen to file in two formats"""
    try:
        with open(filepath + '.emu', 'w', encoding='utf-8') as f:
            f.write(screen.emubuffer)
        with open(filepath + '.brp', 'w', encoding='utf-8') as g:
            g.write(screen.colorbuffer)
        return True, f'Screen saved to {filepath}.emu and {filepath}.brp'
    except Exception as e:
        return False, f'Error saving screen: {e}'
