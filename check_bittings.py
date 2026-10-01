#!/usr/bin/env python3
"""Run `check_bittings` straight from a checkout (same as `python3 -m sfic_solver.check_bittings`)."""
import sys

from sfic_solver.check_bittings import main

if __name__ == "__main__":
    sys.exit(main())
