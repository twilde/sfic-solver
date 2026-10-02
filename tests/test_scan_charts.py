"""The sfic-scan-charts command: failures, privacy promises, and a run on a PDF."""
import contextlib
import io
import os
import random
import socket
import stat
import subprocess
import sys

import pytest

from conftest import ROOT, run_script
from sfic_solver import charts, check_charts, scan_charts, scanning
from test_scan_setup import run_blocked


def test_help_works_without_the_scan_packages_and_without_tesseract():
    run = run_blocked('''
        import sys
        from sfic_solver import scan_charts
        try:
            scan_charts.main(["--help"])
        except SystemExit as exit:
            print("exit", exit.code)
    ''')
    assert run.returncode == 0, run.stderr
    assert "exit 0" in run.stdout and "check_charts" in run.stdout


def test_without_the_packages_and_without_tesseract_it_exits_2_and_says_what_is_missing(tmp_path):
    scan = tmp_path / "s.png"
    scan.write_bytes(b"x")
    run = run_blocked(f'''
        import os, sys
        os.environ["PATH"] = ""
        os.environ.pop("SFIC_TESSERACT", None)
        from sfic_solver import scan_charts
        sys.exit(scan_charts.main([{str(scan)!r}]))
    ''')
    assert run.returncode == 2
    for needed in ("Pillow", "numpy", "pypdfium2", "Tesseract", 'pip install -e ".[scan]"',
                   "brew install tesseract"):
        assert needed in run.stderr
    assert "Traceback" not in run.stderr


def test_a_missing_input_exits_2_naming_its_position_not_its_name(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(scanning, "require", lambda tesseract=None: "/bin/true")
    pytest.importorskip("PIL")
    assert scan_charts.main([str(tmp_path / "SECRET-NOWHERE.pdf")]) == 2
    err = capsys.readouterr().err
    assert "input 1: not a file or a directory" in err and "SECRET" not in err


def test_existing_output_files_stop_the_run_before_anything_is_read(tmp_path, monkeypatch, capsys):
    pytest.importorskip("PIL")
    monkeypatch.setattr(scanning, "require", lambda tesseract=None: "/bin/true")
    scan = tmp_path / "scans.png"
    scan.write_bytes(b"x")
    # (an unreadable image would fail later: the point is that we never get that far)
    (tmp_path / "scans.review.txt").write_text("keep")
    assert scan_charts.main([str(scan)]) == 2
    err = capsys.readouterr().err
    assert "already exist" in err and "scans.review.txt" in err
    assert (tmp_path / "scans.review.txt").read_text() == "keep"


def test_the_root_script_runs_as_a_command():
    run = run_script("scan_charts", "--help")
    assert run.returncode == 0 and "NAME.review.txt" in run.stdout


# --- a whole run on a PDF made at test time ------------------------------------------

from scan_helpers import have_tesseract, need_fonts, random_chart, render  # noqa: E402


def erase_cell(image, line_index, cell_index):
    from PIL import ImageDraw
    from sfic_solver.scanning import clean, layout
    found = layout.analyse(clean.prepare(image))
    line = found.lines[line_index]
    token = line.tokens[1 + cell_index]
    ImageDraw.Draw(image).rectangle((token.x0 - 3, line.y0 - 3, token.x1 + 3, line.y1 + 3),
                                    fill=255)
    return image


@pytest.fixture(scope="module")
def cli_run(tmp_path_factory):
    """Run the command in-process on a 5-page PDF (four clean charts, one with a cell
    erased), with TMPDIR pointing at an empty directory and sockets forbidden."""
    pytest.importorskip("PIL")
    pytest.importorskip("pypdfium2")
    if not have_tesseract():
        pytest.skip("Tesseract is not installed")
    work = tmp_path_factory.mktemp("cli")
    quiet = tmp_path_factory.mktemp("tmp")                 # must stay empty
    truths, images = [], []
    for seed in range(1, 5):
        lines, truth = random_chart(random.Random(seed))
        images.append(render(lines, seed=seed).convert("L"))
        truths.append(truth)
    lines, truth = random_chart(random.Random(5))
    images.append(erase_cell(render(lines), 5, 2))
    truths.append(truth)
    pdf = work / "paper.pdf"
    images[0].save(pdf, save_all=True, append_images=images[1:], resolution=300)

    out, err = io.StringIO(), io.StringIO()
    real_socket, real_tmp = socket.socket, os.environ.get("TMPDIR")

    def no_network(*args, **kwargs):
        raise AssertionError("the scanner tried to open a socket")

    socket.socket = no_network
    os.environ["TMPDIR"] = str(quiet)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = scan_charts.main([str(pdf), "-o", str(work / "result"), "--jobs", "4"])
    finally:
        socket.socket = real_socket
        if real_tmp is None:
            os.environ.pop("TMPDIR")
        else:
            os.environ["TMPDIR"] = real_tmp
    return {"code": code, "out": out.getvalue(), "err": err.getvalue(), "work": work,
            "quiet": quiet, "truths": truths}


def parse(path):
    return charts.parse_charts(path.read_text())


pytestmark_run = [need_fonts()]


@need_fonts()
def test_a_run_with_a_flagged_chart_exits_1_and_writes_two_files(cli_run):
    assert cli_run["code"] == 1
    work = cli_run["work"]
    assert (work / "result.txt").exists() and (work / "result.review.txt").exists()
    assert not (work / "result.failed.txt").exists()


@need_fonts()
def test_the_accepted_file_holds_the_clean_charts_as_drawn_and_check_charts_agrees(cli_run):
    accepted = parse(cli_run["work"] / "result.txt")
    assert len(accepted) == 4
    for chart, truth in zip(accepted, cli_run["truths"]):
        assert chart.control == truth["control"]
        assert [(label, [None if c is None else str(c) for c in cells])
                for label, cells in chart.rows] == \
            [(label.lower(), [None if c == "--" else c for c in cells])
             for label, cells in truth["rows"]]
        assert check_charts.check_chart(chart) == []
    run = subprocess.run([sys.executable, str(ROOT / "check_charts.py"),
                          str(cli_run["work"] / "result.txt")], capture_output=True, text=True)
    assert run.returncode == 0 and "OK" in run.stdout


@need_fonts()
def test_the_review_file_is_refused_by_check_charts_and_names_its_problem(cli_run):
    text = (cli_run["work"] / "result.review.txt").read_text()
    assert "??" in text
    with pytest.raises(charts.ChartError):
        charts.parse_charts(text)
    assert "input 1, page 5, chart 1: needs review" in cli_run["out"]
    assert "row 2 (Control) does not have one cell per chamber" in cli_run["out"]


@need_fonts()
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file modes")
def test_the_files_are_private(cli_run):
    for name in ("result.txt", "result.review.txt"):
        assert stat.S_IMODE((cli_run["work"] / name).stat().st_mode) == 0o600


@need_fonts()
def test_nothing_was_written_to_the_temporary_directory_and_no_socket_was_opened(cli_run):
    assert list(cli_run["quiet"].iterdir()) == []
    assert "socket" not in cli_run["err"]               # an attempt would have raised


@need_fonts()
def test_the_report_has_positions_and_no_digit_names_or_paths(cli_run):
    out = cli_run["out"]
    assert "input 1, page 1, chart 1: accepted" in out
    assert "4 chart(s) accepted" in out and "1 need review" in out
    for truth in cli_run["truths"]:
        assert truth["control"] not in out and truth["master"] not in out
    assert "paper" not in out and "result" not in out
    assert "wrote 4 accepted chart(s)" in cli_run["err"]        # paths are on stderr only
