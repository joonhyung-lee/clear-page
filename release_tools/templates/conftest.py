"""pytest runs from the package root; add utils/ and models/ like utils/tools/run.py does."""
from tools.run import PATHS
import sys

sys.path[:0] = PATHS
