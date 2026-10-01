#!/usr/bin/env python3
"""Run `gen_bittings` straight from a checkout (same as `python3 -m sfic_solver.gen_bittings`)."""
import sys

from sfic_solver.gen_bittings import main

if __name__ == "__main__":
    sys.exit(main())
