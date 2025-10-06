import os
from pyeuropepmc.parser import EuropePMCParser, ParsingError

def list_fixtures(fixture_dir):
    files = []
    for root, dirs, filenames in os.walk(fixture_dir):
        for fname in filenames:
            if fname.endswith((".json", ".xml", ".dc.xml", ".ris", ".bib", ".csv")):
                files.append(os.path.join(root, fname))
    return files

def interactive_fixture_parser_test():
    fixture_dir = os.path.join(os.path.dirname(__file__), "../../fixtures")
    fixtures = list_fixtures(fixture_dir)
    print("EuropePMCParser Interactive Fixture Test")
    print("Available fixture files:")
    for idx, fpath in enumerate(fixtures):
        print(f"{idx+1}. {fpath}")
    choice = input("Select fixture file by number: ").strip()
    try:
        idx = int(choice) - 1
        fpath = fixtures[idx]
    except Exception:
        print("Invalid selection.")
        return
    import json
    with open(fpath, "r", encoding="utf-8") as f:
        if fpath.endswith(".json"):
            try:
                raw_input = json.load(f)
                raw_input_str = str(raw_input)[:1000] + ("..." if len(str(raw_input)) > 1000 else "")
            except Exception as e:
                print(f"Error loading JSON: {e}")
                return
        else:
            raw_input = f.read()
            raw_input_str = raw_input[:1000] + ("..." if len(raw_input) > 1000 else "")
    print("\nRaw input from fixture:")
    print(raw_input_str)
    print("\nSelect parser function:")
    print("1. parse_xml")
    print("2. parse_json")
    print("3. parse_dc")
    print("4. parse_ris")
    print("5. parse_bibtex")
    print("6. parse_csv")
    parser_map = {
        "1": EuropePMCParser.parse_xml,
        "2": EuropePMCParser.parse_json,
        "3": EuropePMCParser.parse_dc,
        "4": EuropePMCParser.parse_ris,
        "5": EuropePMCParser.parse_bibtex,
        "6": EuropePMCParser.parse_csv,
    }
    choice = input("Enter number: ").strip()
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
    interactive_fixture_parser_test()
