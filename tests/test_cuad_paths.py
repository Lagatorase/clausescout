"""Matching CUAD titles to PDF filenames, with a fake index so no dataset is needed."""

from pathlib import Path

from clausescout.data import cuad


def test_pdf_matching_handles_spaces_accents_dashes_and_suffixes(monkeypatch):
    stems = [
        "Acme - Supply Agreement ",            # trailing space in the filename
        "LECLANCHE\u0301 S.A. - JDA",          # decomposed accent
        "NETGEAR-EX-10.16-AMENDMENT-",         # trailing dash
        "Harpoon_EX-10.18_Development Agreement_Option Agreement",  # extra suffix
        "Beta - License", "Beta - License Amendment",
    ]
    fake = {cuad._pdf_key(s): Path(f"{s}.pdf") for s in stems}
    monkeypatch.setattr(cuad, "_pdf_index", lambda: fake)
    assert cuad.pdf_path("Acme - Supply Agreement") == Path("Acme - Supply Agreement .pdf")
    assert cuad.pdf_path("LECLANCH\u00c9 S.A. - JDA") is not None
    assert cuad.pdf_path("NETGEAR-EX-10.16-AMENDMENT") is not None
    assert cuad.pdf_path("Harpoon_EX-10.18_Development Agreement") is not None
    # "Beta - License" matches exactly, even though it is also a prefix of another file.
    assert cuad.pdf_path("Beta - License") == Path("Beta - License.pdf")
    # An ambiguous prefix gives no match rather than a guess.
    assert cuad.pdf_path("Beta") is None
