from pyeuropepmc.processing.parser import EuropePMCParser

class TestEuropePMCParserFormats:

    def test_parse_csv_basic(self):
        csv = "author,title,year\nJohn Smith,Sample Article,2023\nJane Doe,Another Title,2022\n"
        results = EuropePMCParser.parse_csv(csv)
        assert isinstance(results, list)
        assert len(results) == 2
        assert results[0]['author'] == 'John Smith'
        assert results[1]['title'] == 'Another Title'


    def test_parse_csv_error(self):
        # Malformed CSV should not raise, just return best effort
        csv = "author,title\nJohn Smith,Sample Article\nJane Doe"
        results = EuropePMCParser.parse_csv(csv)
        assert isinstance(results, list)
