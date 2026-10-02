#!/usr/bin/env python3
"""Run `scan_charts` straight from a checkout (same as `python3 -m sfic_solver.scan_charts`)."""
import sys

from sfic_solver.scan_charts import main

if __name__ == "__main__":
    sys.exit(main())
