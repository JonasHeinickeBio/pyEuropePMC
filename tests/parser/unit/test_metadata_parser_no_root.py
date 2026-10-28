"""MetadataParser without parsed XML raises ParsingError, also under ``python -O``."""

import subprocess
import sys

import pytest

from pyeuropepmc.core.exceptions import ParsingError
from pyeuropepmc.features.fulltext.parsers.metadata_parser import MetadataParser

METHODS = [
    "_extract_journal_metadata",
    "_extract_extended_metadata",
    "_extract_copyright",
    "_extract_history_dates",
    "_extract_corresp",
    "_extract_counts",
]


@pytest.mark.parametrize("method", METHODS)
def test_missing_root_is_a_parsing_error(method):
    parser = MetadataParser(root=None)
    with pytest.raises(ParsingError):
        getattr(parser, method)()


def test_missing_root_is_checked_under_optimize_flag():
    code = (
        "from pyeuropepmc.core.exceptions import ParsingError\n"
        "from pyeuropepmc.features.fulltext.parsers.metadata_parser import MetadataParser\n"
        "try:\n"
        "    MetadataParser(root=None)._extract_journal_metadata()\n"
        "except ParsingError:\n"
        "    raise SystemExit(0)\n"
        "raise SystemExit(1)\n"
    )
    done = subprocess.run([sys.executable, "-O", "-c", code], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
