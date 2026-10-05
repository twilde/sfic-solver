"""pin_system: the charts it prints are the design's, and the reader and checker accept them."""
import json
import re
import subprocess
import sys

import pytest

from conftest import FIXTURES, ROOT, call_main, run_script
from sfic_solver import charts, pin_system
from sfic_solver.check_charts import check_chart

PINNING = FIXTURES / "pinning.json"
DATE = "2026-10-01"


def chart_text(*extra, path=PINNING):
    proc = run_script("pin_system", path, "--date", DATE, *extra)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


def doc_charts():
    """The three example charts in the core pinning document, as text."""
    text = (ROOT / "docs" / "designs" / "core-pinning.md").read_text()
    block = re.search(r"```\n(Key System = .*?)```", text, re.S).group(1)
    return [part.strip() + "\n" for part in re.split(r"\n-{10,}\n", block)]


def write(tmp_path, raw, name="system.json"):
    path = tmp_path / name
    path.write_text(json.dumps(raw))
    return path


@pytest.fixture
def pinned():
    return json.loads(PINNING.read_text())


def test_the_design_documents_example_charts_are_what_the_command_prints():
    out = chart_text()
    examples = doc_charts()
    assert len(examples) == 3
    for example in examples:
        assert example in out, example


def test_every_core_and_every_unit_key_gets_a_chart_the_reader_and_checker_accept():
    parsed = charts.parse_charts(chart_text())
    assert [c.metadata[1][1] for c in parsed] == [
        "Area A cores", "Area B cores", "Area C cores", "Sub-master cores", "Standalone cores",
        "Unit cores (unit:101)", "Unit cores (unit:102)", "Unit cores (unit:103)"]
    for chart in parsed:
        assert chart.layout == "tools" and chart.system == "A2"
        assert check_chart(chart) == []          # the pinner, checked against what was printed


def test_the_header_is_in_the_documented_order_and_repeated_for_every_chart():
    out = chart_text()
    headers = re.findall(r"^(Key System|System|Core|Date|Control Key) = ", out, re.M)
    assert headers == ["Key System", "System", "Core", "Date", "Control Key"] * 8
    assert out.count(f"Date = {DATE}") == 8 and out.count("Key System = Example building") == 8


def test_charts_are_separated_by_a_line_of_dashes_with_a_blank_line_either_side():
    out = chart_text()
    assert out.count("\n\n" + "-" * 40 + "\n\n") == 7
    assert out.endswith("\n") and not out.endswith("\n\n")


def test_a_unit_core_names_its_key_and_a_core_with_one_change_key_does_not():
    out = chart_text()
    assert "Core = Unit cores (unit:101)" in out and "Core = Standalone cores\n" in out


def test_a_core_with_several_change_keys_names_each_key(pinned, tmp_path):
    pinned["cores"][0]["change"] = ["area_a", "area_b"]
    out = chart_text(path=write(tmp_path, pinned))
    assert "Core = Area A cores (area_a)" in out and "Core = Area A cores (area_b)" in out


def test_without_a_name_the_key_system_line_is_left_out(pinned, tmp_path):
    del pinned["name"]
    out = chart_text(path=write(tmp_path, pinned))
    assert "Key System" not in out
    assert len(charts.parse_charts(out)) == 8


def test_the_date_defaults_to_today(monkeypatch, capsys):
    monkeypatch.setattr(pin_system, "today", lambda: "2031-02-03")
    assert call_main(pin_system.main, [PINNING], monkeypatch) == 0
    assert capsys.readouterr().out.count("Date = 2031-02-03") == 8


@pytest.mark.parametrize("bad", ["2026-13-01", "2026-02-30", "2026/10/01", "tomorrow", "2026-1-1"])
def test_a_date_must_be_a_real_date_written_year_month_day(bad):
    proc = run_script("pin_system", PINNING, "--date", bad)
    assert proc.returncode == 2 and "is not a date written YYYY-MM-DD" in proc.stderr
    assert proc.stdout == "" and "Traceback" not in proc.stderr


def test_a_file_without_pinning_is_refused_with_a_clear_message(pinned, tmp_path):
    del pinned["pinning"]
    for core in pinned["cores"]:
        del core["control"]
    proc = run_script("pin_system", write(tmp_path, pinned))
    assert proc.returncode == 1 and proc.stdout == ""
    assert "does not set pinning" in proc.stderr and "Traceback" not in proc.stderr


def test_a_null_bitting_is_refused_by_the_loader(pinned, tmp_path):
    pinned["keys"]["unit_master"] = None
    proc = run_script("pin_system", write(tmp_path, pinned))
    assert proc.returncode == 1 and "bitting is unknown (null)" in proc.stderr
    assert proc.stdout == ""


def test_a_core_that_cannot_be_pinned_stops_the_whole_run_and_says_where(pinned, tmp_path):
    pinned["keys"]["master_sub"] = "6" + pinned["keys"]["master_sub"][1:]    # 1 from area_a's 5
    proc = run_script("pin_system", write(tmp_path, pinned), "--date", DATE)
    assert proc.returncode == 1 and proc.stdout == ""
    assert ("UNPINNABLE Area A cores [area_a], chamber 1: operating cuts 5 and 6 are 1 apart"
            in proc.stderr)
    assert "no charts printed" in proc.stderr


def test_the_unpinnable_list_is_capped(pinned, tmp_path):
    unit = pinned["keys"]["unit:101"]
    for number in range(40):
        pinned["keys"][f"unit:{200 + number}"] = f"8{number:02d}" + unit[3:]   # 1 from unit_master
    proc = run_script("pin_system", write(tmp_path, pinned))
    lines = proc.stderr.splitlines()
    assert len([ln for ln in lines if ln.startswith("UNPINNABLE")]) == 30
    assert any(re.fullmatch(r"\.\.\. and \d+ more", ln) for ln in lines)


def test_out_writes_a_file_and_prints_only_a_reminder(tmp_path):
    target = tmp_path / "charts.txt"
    proc = run_script("pin_system", PINNING, "--date", DATE, "--out", target)
    assert proc.returncode == 0 and proc.stdout == ""
    assert f"wrote 8 chart(s) to {target}" in proc.stderr and "key data" in proc.stderr
    assert target.read_text() == chart_text()


def test_out_does_not_replace_an_existing_file_unless_forced(tmp_path):
    target = tmp_path / "charts.txt"
    target.write_text("keep me")
    proc = run_script("pin_system", PINNING, "--out", target)
    assert proc.returncode == 1 and "exists; give --force" in proc.stderr
    assert target.read_text() == "keep me"
    forced = run_script("pin_system", PINNING, "--date", DATE, "--out", target, "--force")
    assert forced.returncode == 0 and target.read_text() == chart_text()


def test_a_bad_out_path_is_a_one_line_error_and_writes_nothing(tmp_path):
    missing = tmp_path / "NOT_A_REAL_DIR" / "charts.txt"
    proc = run_script("pin_system", PINNING, "--out", missing)
    assert proc.returncode == 1 and f"error: cannot write {missing}" in proc.stderr
    assert "Traceback" not in proc.stderr and not missing.parent.exists()
    directory = tmp_path / "a_directory"
    directory.mkdir()
    proc = run_script("pin_system", PINNING, "--out", directory, "--force")
    assert proc.returncode == 1 and f"error: cannot write {directory}" in proc.stderr
    assert "Traceback" not in proc.stderr


def test_the_console_script_and_module_forms_work(monkeypatch, capsys):
    assert call_main(pin_system.main, [PINNING, "--date", DATE], monkeypatch) == 0
    assert capsys.readouterr().out == chart_text()
    proc = subprocess.run([sys.executable, "-m", "sfic_solver.pin_system", str(PINNING),
                           "--date", DATE], capture_output=True, text=True, cwd=ROOT)
    assert proc.returncode == 0 and proc.stdout == chart_text()


def test_no_chart_for_a_system_with_a_changed_key_is_stale(pinned, tmp_path):
    """The chart is computed from the file each time: change a key, the pins change."""
    before = chart_text()
    old = pinned["keys"]["area_d"]
    pinned["keys"]["area_d"] = old[:-1] + str((int(old[-1]) + 2) % 10)
    after = chart_text(path=write(tmp_path, pinned))
    assert after != before and f"area_d = {pinned['keys']['area_d']}" in after
