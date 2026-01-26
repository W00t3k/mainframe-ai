"""File operations for saving/loading history"""
import pickle
from os import path

def save_history(history, savefile):
    """Save history to pickle file"""
    if path.exists(savefile):
        return False, "File exists"
    try:
        with open(savefile, 'wb') as sav:
            pickle.dump(history, sav)
        return True, "Saved successfully"
    except Exception as e:
        return False, str(e)

def load_history(loadfile):
    """Load history from pickle file"""
    if not path.exists(loadfile):
        raise FileNotFoundError(f"History file not found: {loadfile}")
    try:
        with open(loadfile, 'rb') as lod:
            hist = pickle.load(lod)
        return hist
    except Exception as e:
        raise ValueError(f"Error loading history: {e}")
