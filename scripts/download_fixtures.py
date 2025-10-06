import os

from pyeuropepmc.fulltext import FullTextClient

# Example PMCIDs (replace with real ones if needed)
PMCIDS = ["PMC3258128", "PMC1911200", "PMC3312970", "PMC3257301", "PMC3359999"]
FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "../tests/fixtures")

os.makedirs(FIXTURE_DIR, exist_ok=True)

client = FullTextClient()

for pmcid in PMCIDS:
    # Download XML
    try:
        xml_content = client.get_fulltext_content(pmcid, format_type="xml")
        xml_path = os.path.join(FIXTURE_DIR, f"{pmcid}.xml")
        with open(xml_path, "w", encoding="utf-8") as f:
            f.write(xml_content)
        print(f"Saved XML for {pmcid} to {xml_path}")
    except Exception as e:
        print(f"Failed to download XML for {pmcid}: {e}")
    # Download PDF
    try:
        pdf_path = os.path.join(FIXTURE_DIR, f"{pmcid}.pdf")
        pdf_file = client.download_pdf_by_pmcid(pmcid, output_path=pdf_path)
        print(f"Saved PDF for {pmcid} to {pdf_path}")
    except Exception as e:
        print(f"Failed to download PDF for {pmcid}: {e}")
