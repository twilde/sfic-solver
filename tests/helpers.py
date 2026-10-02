"""Shared helpers for the tests that read the example charts in the design document."""
import re

from conftest import ROOT


def example_charts():
    """The charts in the core pinning document: (header keys, control, rows by label)."""
    text = (ROOT / "docs" / "designs" / "core-pinning.md").read_text()
    block = re.search(r"```\n(Key System = .*?)```", text, re.S).group(1)
    charts = []
    for chart in re.split(r"\n-{10,}\n", block):
        header, _, body = chart.strip().partition("\n\n")
        fields = dict(re.findall(r"^(.+?) = (.+)$", header, re.M))
        assert header.splitlines()[:5] == [
            f"{label} = {fields[label]}"
            for label in ("Key System", "System", "Core", "Date", "Control Key")]
        control = fields["Control Key"]
        reserved = {"Key System", "System", "Core", "Date", "Control Key"}
        keys = [v for k, v in fields.items() if k not in reserved]
        charts.append((fields, keys, control, parse_rows(body)))
    return charts


def parse_rows(body):
    rows = []
    for line in body.strip().splitlines():
        label, *cells = line.split()
        rows.append((label, [None if c == "--" else int(c) for c in cells]))
    return rows
