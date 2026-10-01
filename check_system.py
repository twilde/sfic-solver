#!/usr/bin/env python3
"""Run `check_system` straight from a checkout (same as `python3 -m sfic_solver.check_system`)."""
import sys

from sfic_solver.check_system import main

if __name__ == "__main__":
    sys.exit(main())
