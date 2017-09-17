# coding: utf-8

"""FETCH parser tests."""

import unittest

from modoboa_webmail.lib.fetch_parser import FetchResponseParser

from . import data


class FetchParserTestCase(unittest.TestCase):
    """Test FETCH parser."""

    def test_parse_bodystructure(self):
        """Test the parsing of several responses containing BS."""
        p = FetchResponseParser()
        r = p.parse(data.BODYSTRUCTURE_SAMPLE_1)
        r = p.parse(data.BODYSTRUCTURE_SAMPLE_2)
        r = p.parse(data.BODYSTRUCTURE_SAMPLE_3)
        r = p.parse(data.BODYSTRUCTURE_SAMPLE_4)
        r = p.parse(data.BODYSTRUCTURE_SAMPLE_5)
        r = p.parse(data.BODYSTRUCTURE_SAMPLE_6)
        r = p.parse(data.BODYSTRUCTURE_SAMPLE_7)
