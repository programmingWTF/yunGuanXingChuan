"""
Path helper — ensure project root is in sys.path.
Import this FIRST in any module before other project imports.
Usage:  import _path; from src.xxx import yyy
"""
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
