"""pytest runs from the package root; add utils/ and models/ like utils/run.py does."""
from run import PATHS
import sys

sys.path[:0] = PATHS
