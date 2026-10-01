#!/usr/bin/env python3
"""Run `solve_system` straight from a checkout (same as `python3 -m sfic_solver.solve_system`)."""
import sys

from sfic_solver.solve_system import main

if __name__ == "__main__":
    sys.exit(main())
