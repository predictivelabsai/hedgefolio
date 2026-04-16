"""Unit tests for the EDGAR daily-index parser."""

from __future__ import annotations

from datetime import date

SAMPLE_INDEX = """\
Description:           Daily Index of EDGAR Dissemination Feed by Form Type
Last Data Received:    Apr 15, 2026
Comments:              webmaster@sec.gov
Anonymous FTP:         ftp://ftp.sec.gov/edgar/




Form Type   Company Name                                                  CIK         Date Filed  File Name
---------------------------------------------------------------------------------------------------------------------------------------------
10-D             AMERICAN EXPRESS CREDIT ACCOUNT MASTER TRUST                  1003509     20260415    edgar/data/1003509/0001104659-26-043659.txt
SCHEDULE 13D     Veradace Capital Management LLC                               1772351     20260415    edgar/data/1772351/0001772351-26-000007.txt
SCHEDULE 13D/A   VisionWave Holdings, Inc.                                     2038439     20260415    edgar/data/2038439/0001731122-26-000581.txt
SCHEDULE 13G     Passive Fund, LP                                              9999999     20260415    edgar/data/9999999/0009999999-26-000001.txt
SCHEDULE 13G/A   Strickler Jesse                                               1961099     20260415    edgar/data/1961099/0001961099-26-000004.txt
SC 13E3          KORE Group Holdings, Inc.                                     1855457     20260415    edgar/data/1855457/0001140361-26-014631.txt
"""


def test_33_parser_filters_only_13d_and_13g():
    from utils.activist import _parse_index_lines, ACTIVIST_FORMS
    rows = list(_parse_index_lines(SAMPLE_INDEX))
    forms = [r[0] for r in rows]
    assert len(rows) == 4, f"expected 4 activist rows, got {len(rows)}: {forms}"
    assert set(forms).issubset(ACTIVIST_FORMS)
    # Both amendments and non-amendments, both activist + passive variants
    assert "SCHEDULE 13D" in forms
    assert "SCHEDULE 13D/A" in forms
    assert "SCHEDULE 13G" in forms
    assert "SCHEDULE 13G/A" in forms


def test_34_parser_extracts_fields():
    from utils.activist import _parse_index_lines
    rows = list(_parse_index_lines(SAMPLE_INDEX))
    for form, company, cik, fd, path in rows:
        assert cik.isdigit()
        assert isinstance(fd, date)
        assert fd == date(2026, 4, 15)
        assert path.startswith("edgar/data/")
        assert company  # non-empty


def test_35_accession_extractor():
    from utils.activist import _accession_from_path
    acc = _accession_from_path("edgar/data/1772351/0001772351-26-000007.txt")
    assert acc == "0001772351-26-000007"
    # Invalid paths should return None
    assert _accession_from_path("edgar/data/1772351/index.json") is None
    assert _accession_from_path("random.txt") is None
