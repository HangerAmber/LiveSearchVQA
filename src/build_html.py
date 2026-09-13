"""Legacy entry point: build the current anonymous English demo, without APIs."""
import runpy
from pathlib import Path

if __name__=='__main__':
    runpy.run_path(str(Path(__file__).with_name('build_demo.py')),run_name='__main__')
