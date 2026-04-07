"""Unit tests for PubTator Central enrichment client."""

import pytest
from unittest.mock import patch

from pyeuropepmc.enrichment.pubtator import PubTatorClient


class TestPubTatorClient:
    """Tests for PubTatorClient."""

    def test_initialization(self):
        """Test basic initialization."""
        client = PubTatorClient()
        assert client.base_url == PubTatorClient.BASE_URL

    @patch.object(PubTatorClient, "_make_request")
    def test_enrich_without_pmid_raises(self, mock_request):
        """Test that enrich without PMID raises ValueError."""
        client = PubTatorClient()
        with pytest.raises(ValueError, match="Identifier \\(PMID or PMCID\\) is required"):
            client.enrich()

    @patch.object(PubTatorClient, "_make_request")
    def test_enrich_success(self, mock_request):
        """Test successful enrichment with PubTator data."""
        # Mock PubTator BioC XML response
        mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
<collection>
<document>
<id>12345</id>
<passage>
<text>BRCA1 gene is associated with breast cancer.</text>
<annotation id="1">
<infon key="type">Gene</infon>
<location offset="0" length="5"/>
<text>BRCA1</text>
<infon key="identifier">MESH:D000071877|HGNC:1100|NCBIGENE:672</infon>
</annotation>
<annotation id="2">
<infon key="type">Disease</infon>
<location offset="32" length="13"/>
<text>breast cancer</text>
<infon key="identifier">MESH:D001943</infon>
</annotation>
</passage>
</document>
</collection>"""
        mock_request.return_value = mock_xml

        client = PubTatorClient()
        result = client.enrich(identifier="12345")

        assert result is not None
        assert result["source"] == "pubtator"
        assert result["pmid"] == "12345"
        assert len(result["entities"]) == 2

        # Check gene entity
        gene = result["entities"][0]
        assert gene["type"] == "Gene"
        assert gene["text"] == "BRCA1"
        assert gene["id"] == "MESH:D000071877|HGNC:1100|NCBIGENE:672"

        # Check disease entity
        disease = result["entities"][1]
        assert disease["type"] == "Disease"
        assert disease["text"] == "breast cancer"
        assert disease["id"] == "MESH:D001943"

    @patch.object(PubTatorClient, "_make_request")
    def test_enrich_no_response(self, mock_request):
        """Test enrichment when API returns None."""
        mock_request.return_value = None

        client = PubTatorClient()
        result = client.enrich(identifier="12345")

        assert result is None

    @patch.object(PubTatorClient, "_make_request")
    def test_enrich_empty_xml(self, mock_request):
        """Test enrichment with empty XML."""
        mock_request.return_value = "<collection></collection>"

        client = PubTatorClient()
        result = client.enrich(identifier="12345")

        assert result is None

    @patch.object(PubTatorClient, "_make_request")
    def test_enrich_malformed_xml(self, mock_request):
        """Test enrichment with malformed XML."""
        mock_request.return_value = "<invalid>xml"

        client = PubTatorClient()
        result = client.enrich(identifier="12345")

        assert result is None

    @patch.object(PubTatorClient, "_make_request")
    def test_enrich_with_relations(self, mock_request):
        """Test enrichment with entity relations."""
        mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
<collection>
<document>
<id>12345</id>
<passage>
<text>BRCA1 gene is associated with breast cancer.</text>
<annotation id="1">
<infon key="type">Gene</infon>
<text>BRCA1</text>
<infon key="identifier">NCBIGENE:672</infon>
</annotation>
<annotation id="2">
<infon key="type">Disease</infon>
<text>breast cancer</text>
<infon key="identifier">MESH:D001943</infon>
</annotation>
<relation id="1">
<infon key="type">Association</infon>
<node refid="1" role="Gene"/>
<node refid="2" role="Disease"/>
</relation>
</passage>
</document>
</collection>"""
        mock_request.return_value = mock_xml

        client = PubTatorClient()
        result = client.enrich(identifier="12345")

        assert result is not None
        assert len(result["relations"]) == 1
        relation = result["relations"][0]
        assert relation["type"] == "Association"
        assert len(relation["nodes"]) == 2
