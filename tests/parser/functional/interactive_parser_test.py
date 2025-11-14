import sys
from pyeuropepmc.processing.parser import EuropePMCParser, ParsingError

def interactive_parser_test():
    print("EuropePMCParser Interactive Test")
    print("Enter raw input (XML, JSON, DC, RIS, BibTeX, CSV). End with Ctrl+D (Linux/Mac) or Ctrl+Z (Windows):")
    raw_input = sys.stdin.read()
    print("\nRaw input received:")
    print(raw_input)
    print("\nSelect parser function:")
    print("1. parse_xml")
    print("2. parse_json")
    print("3. parse_dc")
    print("4. parse_ris")
    print("5. parse_bibtex")
    print("6. parse_csv")
    choice = input("Enter number: ").strip()
    parser_map = {
        "1": EuropePMCParser.parse_xml,
        "2": EuropePMCParser.parse_json,
        "3": EuropePMCParser.parse_dc,
        "4": EuropePMCParser.parse_ris,
        "5": EuropePMCParser.parse_bibtex,
        "6": EuropePMCParser.parse_csv,
    }
    parser_func = parser_map.get(choice)
    if not parser_func:
        print("Invalid choice.")
        return
    print("\nProcessing input...")
    try:
        result = parser_func(raw_input)
        print("\nParser output:")
        print(result)
        user_decision = input("\nShould the parser PASS this test? (y/n): ").strip().lower()
        if user_decision == "y":
            print("Test marked as PASS.")
        else:
            print("Test marked as FAIL.")
    except ParsingError as e:
        print(f"\nParsingError: {e}")
        user_decision = input("\nShould the parser FAIL this test? (y/n): ").strip().lower()
        if user_decision == "y":
            print("Test marked as FAIL.")
        else:
            print("Test marked as PASS.")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        user_decision = input("\nShould the parser FAIL this test? (y/n): ").strip().lower()
        if user_decision == "y":
            print("Test marked as FAIL.")
        else:
            print("Test marked as PASS.")

if __name__ == "__main__":
    interactive_parser_test()
