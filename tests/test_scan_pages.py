"""Loading pages from PDFs and images, in memory, with positions and no names."""
import pytest

pytest.importorskip("PIL")
pytest.importorskip("pypdfium2")

from PIL import Image, ImageDraw  # noqa: E402

from sfic_solver.scanning import InputError  # noqa: E402
from sfic_solver.scanning import pages  # noqa: E402


def make_image(tmp_path, name, size=(120, 80), shade=255, **save):
    image = Image.new("L", size, shade)
    ImageDraw.Draw(image).text((5, 5), "x", fill=0)
    image.save(tmp_path / name, **save)
    return tmp_path / name


def read(paths):
    return list(pages.iter_pages(pages.collect_sources(paths)))


def test_an_image_file_is_one_grey_page(tmp_path):
    got = read([make_image(tmp_path, "a.png")])
    assert [(p.source, p.number) for p in got] == [(1, 1)]
    assert got[0].image.mode == "L" and got[0].image.size == (120, 80)


def test_a_multi_page_tiff_is_one_page_per_frame(tmp_path):
    frames = [Image.new("L", (50, 40), v) for v in (255, 200, 100)]
    frames[0].save(tmp_path / "m.tiff", save_all=True, append_images=frames[1:])
    got = read([tmp_path / "m.tiff"])
    assert [(p.source, p.number) for p in got] == [(1, 1), (1, 2), (1, 3)]
    assert got[2].image.getpixel((0, 0)) == 100


def test_a_pdf_is_rendered_at_300_dpi_in_memory(tmp_path):
    # 100 px at 100 dpi is one inch, so the page renders to 300 px at 300 dpi.
    frames = [Image.new("L", (100, 100), 255) for _ in range(2)]
    frames[0].save(tmp_path / "d.pdf", save_all=True, append_images=frames[1:],
                   resolution=100)
    before = sorted(tmp_path.iterdir())
    got = read([tmp_path / "d.pdf"])
    assert [(p.source, p.number) for p in got] == [(1, 1), (1, 2)]
    assert abs(got[0].image.size[0] - 300) <= 2
    assert sorted(tmp_path.iterdir()) == before          # no file was written


def test_transparency_is_flattened_onto_white(tmp_path):
    Image.new("RGBA", (20, 20), (0, 0, 0, 0)).save(tmp_path / "t.png")
    assert read([tmp_path / "t.png"])[0].image.getpixel((3, 3)) == 255


def test_a_directory_is_expanded_in_sorted_order_and_numbered_on(tmp_path):
    folder = tmp_path / "scans"
    folder.mkdir()
    make_image(folder, "b.png")
    make_image(folder, "a.png", shade=10)
    (folder / "notes.md").write_text("not a scan")
    other = make_image(tmp_path, "z.jpg")
    got = pages.collect_sources([folder, other])
    assert [(s.number, s.path.name) for s in got] == [(1, "a.png"), (2, "b.png"), (3, "z.jpg")]
    assert read([folder])[0].image.getpixel((100, 70)) == 10     # a.png came first


def test_unusable_inputs_are_refused_by_position_not_name(tmp_path):
    (tmp_path / "SECRET-BUILDING.txt").write_text("x")
    for bad, reason in ((tmp_path / "SECRET-BUILDING.txt", "not a PDF"),
                        (tmp_path / "SECRET-NOWHERE.png", "not a file or a directory")):
        with pytest.raises(InputError) as err:
            pages.collect_sources([make_image(tmp_path, "ok.png"), bad])
        assert err.value.source == 2 and reason in str(err.value)
        assert "SECRET" not in str(err.value)


def test_an_empty_directory_is_refused(tmp_path):
    with pytest.raises(InputError, match="holds no PDFs or images"):
        pages.collect_sources([tmp_path])


@pytest.mark.parametrize("name, what", [("broken.png", "image"), ("broken.pdf", "PDF")])
def test_a_file_that_cannot_be_read_says_so_without_its_name(tmp_path, name, what):
    (tmp_path / name).write_bytes(b"not really a file")
    with pytest.raises(InputError) as err:
        read([tmp_path / name])
    assert f"cannot be read as a{'n' if what == 'image' else ''} {what}" in str(err.value)
    assert "broken" not in str(err.value)
