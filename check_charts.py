#!/usr/bin/env python3
"""Run `check_charts` straight from a checkout (same as `python3 -m sfic_solver.check_charts`)."""
import sys

from sfic_solver.check_charts import main

if __name__ == "__main__":
    sys.exit(main())
