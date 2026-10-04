"""The conformance command: does the pinner reproduce real charts? Positions only."""
import re

import pytest

from conftest import FIXTURES, run_script
from sfic_solver import charts
from sfic_solver.check_charts import check_chart, main

TOOLS = FIXTURES / "charts" / "tools_layout.txt"
LEGACY = FIXTURES / "charts" / "legacy_layout.txt"

# Everything in the fixtures that identifies a key, a core or a building.
SENSITIVE = ["9743854", "3785412", "5961634", "5721276", "7305496", "9565698", "7587672",
             "3101658", "3323872", "1161012", "area_a", "master_top", "unit_master",
             "Example building", "Area A", "Standalone", "2026-10-01"]


def assert_no_key_data(text):
    assert not [s for s in SENSITIVE if s in text]
    assert not re.search(r"\d{5,}", text), "a long run of digits could be a bitting"


def test_both_fixture_files_agree_with_the_pinner(capsys):
    assert main([str(TOOLS), str(LEGACY)]) == 0
    out = capsys.readouterr().out
    assert "Checked 2 file(s), 6 chart(s), 42 chamber(s): 6 chart(s) agree" in out
    assert out.rstrip().endswith("OK")


def test_a_directory_is_searched_for_txt_files(capsys, tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.txt").write_text(TOOLS.read_text())
    (tmp_path / "b.txt").write_text(LEGACY.read_text())
    (tmp_path / "notes.md").write_text("not a chart")
    assert main([str(tmp_path)]) == 0
    assert "Checked 2 file(s), 6 chart(s)" in capsys.readouterr().out


def test_the_environment_variable_supplies_a_path_when_none_is_given(capsys, monkeypatch):
    monkeypatch.setenv("SFIC_CHARTS", str(LEGACY))
    assert main([]) == 0
    assert "Checked 1 file(s), 3 chart(s)" in capsys.readouterr().out


def test_with_nothing_to_check_it_does_nothing(capsys, monkeypatch):
    monkeypatch.delenv("SFIC_CHARTS", raising=False)
    assert main([]) == 0
    assert "nothing to do" in capsys.readouterr().out


def test_bad_paths_are_usage_errors(tmp_path, capsys):
    for args in ([str(tmp_path / "missing.txt")], [str(tmp_path)]):
        with pytest.raises(SystemExit) as caught:
            main(args)
        assert caught.value.code == 2
    err = capsys.readouterr().err
    assert "not a file or a directory" in err and "no .txt chart files found" in err
    assert str(tmp_path) not in err


def break_chart(text, old, new, count=1):
    assert old in text, old
    return text.replace(old, new, count)


def test_a_wrong_pin_is_reported_by_position_only(tmp_path, capsys):
    # Chart 2 of the tools file, chamber 4: change one pin size in the Bottom row.
    bad = break_chart(TOOLS.read_text(), "Bottom   3  1  0  1  6  5  2",
                      "Bottom   3  1  0  2  6  5  2")
    path = tmp_path / "charts.txt"
    path.write_text(bad)
    assert main([str(path)]) == 1
    out = capsys.readouterr().out
    assert "file 1, chart 2: chamber 4 differs" in out
    assert ("Checked 1 file(s), 3 chart(s), 21 chamber(s): 2 chart(s) agree with the pinner, "
            "1 do not (1 chamber(s)); 0 chart(s) could not be checked; "
            "0 file(s) could not be read.") in out
    assert "DISAGREEMENTS" in out
    assert_no_key_data(out)


def test_details_show_pin_sizes_and_say_not_to_share_them(tmp_path, capsys):
    path = tmp_path / "charts.txt"
    path.write_text(break_chart(TOOLS.read_text(), "Bottom   3  1  0  1  6  5  2",
                                "Bottom   3  1  0  2  6  5  2"))
    assert main([str(path), "--details"]) == 1
    out = capsys.readouterr().out
    assert "do not share" in out
    assert "chamber 4: chart [2, 6, 8, 8], pinner [1, 6, 8, 8]" in out


@pytest.mark.parametrize("line", ["Master Key = 5721276", "Change Keys = 5721276"])
def test_a_legacy_chart_with_a_single_key_line_is_checked(tmp_path, capsys, line):
    """A core with one operating key has no master rows: T/D, Control, Bottom."""
    path = tmp_path / "c.txt"
    path.write_text(f"System = A2\nControl Key = 9743854\n{line}\n\n"
                    "T/D      4  6  9 10  5  8  9\nControl 14 10 12 12 16  8  8\n"
                    "Bottom   5  7  2  1  2  7  6\n")
    assert main([str(path)]) == 0
    out = capsys.readouterr().out
    assert "1 chart(s) agree with the pinner, 0 do not" in out
    assert out.rstrip().endswith("OK")


def test_an_unpinnable_chamber_is_reported_and_explained_only_on_request(tmp_path, capsys):
    # Operating cuts 3 and 4 in the first chamber are 1 apart: no pin that short exists.
    chart_text = (
        "System = A2\nControl Key = 9743854\nMaster Key = 3961634\nChange Keys = 4721276\n\n"
        "T/D      4  6  9 10  5  8  9\nControl 12  8  8  8 12  6  8\n"
        "Master   2  4  2  4  2  4  2\nBottom   5  3  0  1  2  3  4\n")
    path = tmp_path / "c.txt"
    path.write_text(chart_text)
    assert main([str(path)]) == 1
    plain = capsys.readouterr().out
    assert "chamber 1 cannot be pinned" in plain
    assert "apart" not in plain
    assert main([str(path), "--details"]) == 1
    assert "chamber 1: operating cuts 3 and 4 are 1 apart" in capsys.readouterr().out


def test_master_rows_that_do_not_fill_from_the_bottom_are_a_layout_problem(tmp_path, capsys):
    text = LEGACY.read_text()
    swapped = break_chart(text, "Master  --  2 -- -- --  2  2\nMaster   4  2  4  4  4  4  2",
                          "Master   4  2  4  4  4  4  2\nMaster  --  2 -- -- --  2  2")
    path = tmp_path / "c.txt"
    path.write_text(swapped)
    assert main([str(path)]) == 1
    out = capsys.readouterr().out
    assert "file 1, chart 1: chamber 1 has master rows that do not fill from the bottom" in out
    assert "chamber 2" not in out.split("chart 2")[0]       # chamber 2 (1 master) is fine


def test_an_unreadable_chart_is_reported_without_quoting_it(tmp_path, capsys):
    path = tmp_path / "c.txt"
    path.write_text(break_chart(LEGACY.read_text(), "Control Key = 9743854",
                                "Control Key = 974385"))
    assert main([str(path)]) == 1
    out = capsys.readouterr().out
    assert "file 1: chart 1: every key must be digits and as long as the control key" in out
    assert ("Checked 1 file(s), 0 chart(s), 0 chamber(s): 0 chart(s) agree with the pinner, "
            "0 do not (0 chamber(s)); 0 chart(s) could not be checked; "
            "1 file(s) could not be read.") in out
    assert out.rstrip().endswith("PROBLEMS: some charts could not be read or checked")
    assert "DISAGREEMENTS" not in out
    assert_no_key_data(out)


def test_an_unknown_pinning_system_is_reported(tmp_path, capsys):
    path = tmp_path / "c.txt"
    path.write_text(break_chart(LEGACY.read_text(), "System = A2", "System = A9"))
    assert main([str(path)]) == 1
    out = capsys.readouterr().out
    assert "file 1, chart 1: names a pinning system the tools do not have" in out
    assert "A9" not in out and "known systems" not in out
    assert ("Checked 1 file(s), 2 chart(s), 14 chamber(s): 2 chart(s) agree with the pinner, "
            "0 do not (0 chamber(s)); 1 chart(s) could not be checked; "
            "0 file(s) could not be read.") in out
    assert out.rstrip().endswith("PROBLEMS: some charts could not be read or checked")
    assert "DISAGREEMENTS" not in out and "OK" not in out


def test_a_utf8_byte_order_mark_is_fine(tmp_path, capsys):
    path = tmp_path / "c.txt"
    path.write_bytes(b"\xef\xbb\xbf" + LEGACY.read_bytes())          # as Windows tools write it
    assert main([str(path)]) == 0
    assert "Checked 1 file(s), 3 chart(s)" in capsys.readouterr().out


def test_a_file_in_another_encoding_says_it_is_not_utf8(tmp_path, capsys):
    path = tmp_path / "c.txt"
    path.write_bytes(LEGACY.read_bytes().replace(b"Control Key", b"Contr\xf4l Key", 1))
    assert main([str(path)]) == 1
    out = capsys.readouterr().out
    assert "file 1: is not UTF-8 text" in out and "1 file(s) could not be read" in out


@pytest.mark.parametrize("digit", ["\u00b2", "\u0663"])
def test_a_non_ascii_digit_is_an_unreadable_chart_not_a_traceback(tmp_path, capsys, digit):
    path = tmp_path / "c.txt"
    path.write_text(break_chart(LEGACY.read_text(), "T/D      4", f"T/D      {digit}"))
    assert main([str(path)]) == 1
    captured = capsys.readouterr()
    assert "one number (or --) per chamber" in captured.out
    assert digit not in captured.out + captured.err
    assert "Traceback" not in captured.err


def test_a_pinning_system_name_is_not_echoed(tmp_path, capsys):
    path = tmp_path / "c.txt"
    path.write_text(break_chart(LEGACY.read_text(), "System = A2", "System = NOT A REAL SYSTEM 4B"))
    assert main([str(path)]) == 1
    out = capsys.readouterr().out
    assert "NOT A REAL" not in out and "4B" not in out
    assert "names a pinning system the tools do not have" in out
    assert main([str(path), "--details"]) == 1               # the owner can still see it
    assert "NOT A REAL SYSTEM 4B" in capsys.readouterr().out


def test_an_unexpected_error_is_reported_without_quoting_the_chart(tmp_path, capsys, monkeypatch):
    path = tmp_path / "c.txt"
    path.write_text(LEGACY.read_text())
    secret = "ValueError text with 9743854 in it"

    def explode(chart):
        raise ValueError(secret)
    monkeypatch.setattr("sfic_solver.check_charts.check_chart", explode)
    assert main([str(path)]) == 1
    out = capsys.readouterr().out
    assert "file 1, chart 1: could not be checked" in out
    assert "9743854" not in out and "ValueError" not in out
    assert "3 chart(s) could not be checked" in out
    assert main([str(path), "--details"]) == 1
    assert secret in capsys.readouterr().out


def test_an_unexpected_error_while_reading_is_reported_without_quoting(tmp_path, capsys,
                                                                       monkeypatch):
    path = tmp_path / "c.txt"
    path.write_text(LEGACY.read_text())

    def explode(text):
        raise ValueError("secret 9743854")
    monkeypatch.setattr("sfic_solver.charts.parse_charts", explode)
    assert main([str(path)]) == 1
    out = capsys.readouterr().out
    assert "file 1: could not be read (unexpected content)" in out
    assert "secret" not in out and "9743854" not in out


def test_an_unreadable_file_beside_a_disagreeing_chart_is_counted_separately(tmp_path, capsys):
    unreadable = tmp_path / "a.txt"
    unreadable.write_text(break_chart(LEGACY.read_text(), "Control Key = 9743854",
                                      "Control Key = 974385"))
    disagreeing = tmp_path / "b.txt"
    disagreeing.write_text(break_chart(TOOLS.read_text(), "Bottom   3  1  0  1  6  5  2",
                                       "Bottom   3  1  0  2  6  5  2"))
    assert main([str(unreadable), str(disagreeing)]) == 1
    out = capsys.readouterr().out
    assert ("Checked 2 file(s), 3 chart(s), 21 chamber(s): 2 chart(s) agree with the pinner, "
            "1 do not (1 chamber(s)); 0 chart(s) could not be checked; "
            "1 file(s) could not be read.") in out
    assert "-1" not in out
    assert out.rstrip().endswith("DISAGREEMENTS: the pinner's rules do not match these charts")


def test_check_chart_returns_where_and_what():
    chart = charts.parse_charts(LEGACY.read_text())[0]
    assert check_chart(chart) == []
    wrong = charts.Chart(chart.layout, chart.system, chart.control, chart.keys,
                         tuple((label, tuple(c + 1 if c is not None and label == "t/d" else c
                                             for c in cells)) for label, cells in chart.rows))
    assert [(n, kind) for n, kind, _ in check_chart(wrong)] == [(i, "differs") for i in range(1, 8)]


def test_it_runs_as_a_command_from_a_checkout():
    proc = run_script("check_charts", TOOLS, LEGACY)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.rstrip().endswith("OK")
