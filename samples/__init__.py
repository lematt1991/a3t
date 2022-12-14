from glob import glob
import os

def list_samples():
    script_dir = os.path.dirname(os.path.realpath(__file__))
    return glob(os.path.join(script_dir, "*.flac"))