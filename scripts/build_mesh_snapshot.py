"""Build ``src/pyeuropepmc/mcp/data/mesh_common.json`` from the NLM MeSH service.

The ``mesh_expand`` tool works offline from this snapshot of common clinical headings:
descriptor ID, heading, tree numbers and entry terms, all as published by NLM (nothing here is
written by hand except the list of headings to include). Run it again to refresh the snapshot
with the current MeSH release:

    python scripts/build_mesh_snapshot.py

Needs network access to https://id.nlm.nih.gov/mesh/ (public, no key). Headings that NLM does
not know under that exact name are listed and left out.
"""

from __future__ import annotations

import datetime
import json
from pathlib import Path
import sys
import time

import requests

OUT = Path(__file__).parents[1] / "src" / "pyeuropepmc" / "mcp" / "data" / "mesh_common.json"
LOOKUP = "https://id.nlm.nih.gov/mesh/lookup/descriptor"
SPARQL = "https://id.nlm.nih.gov/mesh/sparql"

HEADINGS = """
Diabetes Mellitus; Diabetes Mellitus, Type 1; Diabetes Mellitus, Type 2; Hypertension;
Myocardial Infarction; Heart Failure; Atrial Fibrillation; Stroke; Coronary Artery Disease;
Cardiovascular Diseases; Obesity; Metabolic Syndrome; Asthma; Pulmonary Disease, Chronic
Obstructive; Pneumonia; COVID-19; Influenza, Human; Tuberculosis; HIV Infections; Hepatitis C;
Hepatitis B; Sepsis; Urinary Tract Infections; Malaria; Breast Neoplasms; Lung Neoplasms;
Colorectal Neoplasms; Prostatic Neoplasms; Neoplasms; Leukemia; Lymphoma; Melanoma;
Pancreatic Neoplasms; Depression; Major Depressive Disorder; Anxiety Disorders; Schizophrenia;
Bipolar Disorder; Dementia; Alzheimer Disease; Parkinson Disease; Epilepsy; Multiple Sclerosis;
Migraine Disorders; Sleep Initiation and Maintenance Disorders; Autism Spectrum Disorder;
Attention Deficit Disorder with Hyperactivity; Chronic Pain; Low Back Pain; Osteoarthritis;
Arthritis, Rheumatoid; Osteoporosis; Fractures, Bone; Renal Insufficiency, Chronic;
Inflammatory Bowel Diseases; Crohn Disease; Colitis, Ulcerative; Irritable Bowel Syndrome;
Gastroesophageal Reflux; Liver Cirrhosis; Non-alcoholic Fatty Liver Disease; Pregnancy;
Pre-Eclampsia; Diabetes, Gestational; Premature Birth; Infant, Premature; Depression,
Postpartum; Infertility; Polycystic Ovary Syndrome; Anemia; Venous Thromboembolism; Pulmonary
Embolism; Wounds and Injuries; Burns; Delirium; Frailty; Sarcopenia; Accidental Falls;
Malnutrition; Dehydration; Cognitive Dysfunction; Brain Injuries, Traumatic; Spinal Cord
Injuries; Cerebral Palsy; Hearing Loss; Glaucoma; Macular Degeneration; Cataract; Psoriasis;
Dermatitis, Atopic; Acne Vulgaris; Periodontitis; Dental Caries; Substance-Related Disorders;
Alcohol Drinking; Smoking; Smoking Cessation; Opioid-Related Disorders; Suicide; Burnout,
Professional; Stress, Psychological; Stress Disorders, Post-Traumatic; Metformin; Insulin;
Aspirin; Hydroxymethylglutaryl-CoA Reductase Inhibitors; Antihypertensive Agents;
Angiotensin-Converting Enzyme Inhibitors; Adrenergic beta-Antagonists; Anticoagulants; Warfarin;
Antidepressive Agents; Selective Serotonin Reuptake Inhibitors; Antipsychotic Agents;
Anti-Bacterial Agents;
Antiviral Agents; Anti-Inflammatory Agents, Non-Steroidal; Analgesics, Opioid; Glucocorticoids;
Vitamin D; Probiotics; Dietary Supplements; Fatty Acids, Omega-3; Vaccines; Immunotherapy;
Antineoplastic Agents; Drug Therapy; Radiotherapy; Cognitive Behavioral Therapy; Psychotherapy;
Mindfulness; Exercise; Exercise Therapy; Physical Therapy Modalities; Acupuncture; Yoga;
Diet, Mediterranean; Diet Therapy; Weight Loss; Bariatric Surgery; Laparoscopy; Surgical
Procedures, Operative; Telemedicine; Mobile Applications; Health Education; Behavior Therapy;
Motivational Interviewing; Music Therapy; Massage; Meditation; Breast Feeding; Immunization;
Mass Screening; Palliative Care; Rehabilitation; Anesthesia; Cesarean Section; Respiration,
Artificial; Oxygen Inhalation Therapy; Blood Transfusion; Stents; Percutaneous Coronary
Intervention; Gene Editing; CRISPR-Cas Systems; Machine Learning; Deep Learning; Artificial
Intelligence; Child; Child, Preschool; Infant; Infant, Newborn; Adolescent; Young Adult; Adult;
Middle Aged; Aged; Aged, 80 and over; Pregnant People; Women; Men; Veterans; Students; Nurses;
Physicians; Caregivers; Health Personnel; Intensive Care Units; Hospitalization; Primary Health
Care; Emergency Service, Hospital; Nursing Homes; Rural Population; Urban Population; Health
Status Disparities; Minority Groups; Mortality; Survival; Quality of Life; Treatment Outcome;
Length of Stay; Patient Readmission; Pain Measurement; Blood Pressure; Blood Glucose; Body Mass
Index; Cholesterol; Recurrence; Remission Induction; Drug-Related Side Effects and Adverse
Reactions; Patient Satisfaction; Cost-Benefit Analysis; Disease Progression; Incidence;
Prevalence; Risk Factors; Prognosis; Follow-Up Studies; Randomized Controlled Trials as Topic;
Systematic Reviews as Topic; Meta-Analysis as Topic; Cohort Studies; Case-Control Studies;
Cross-Sectional Studies; Qualitative Research; Interviews as Topic; Focus Groups; Surveys and
Questionnaires; Genome; Genomics; Whole Genome Sequencing; Microbiota; Gastrointestinal
Microbiome; Inflammation; Oxidative Stress; Biomarkers; Magnetic Resonance Imaging; Tomography,
X-Ray Computed; Electroencephalography; Gene Expression; Stem Cells; Genetic Therapy; Pandemics;
Vaccination; Drug Resistance, Microbial
"""


def wanted_headings() -> list[str]:
    return [h.strip() for h in " ".join(HEADINGS.split()).split(";") if h.strip()]


def descriptor_id(session: requests.Session, label: str) -> str | None:
    response = session.get(
        LOOKUP, params={"label": label, "match": "exact", "limit": 5}, timeout=30
    )
    response.raise_for_status()
    for item in response.json():
        if item.get("label", "").lower() == label.lower():
            return str(item["resource"]).rsplit("/", 1)[-1]
    return None


def sparql(session: requests.Session, uis: list[str]) -> list[dict[str, dict[str, str]]]:
    values = " ".join(f"mesh:{ui}" for ui in uis)
    query = f"""
    PREFIX meshv: <http://id.nlm.nih.gov/mesh/vocab#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX mesh: <http://id.nlm.nih.gov/mesh/>
    SELECT ?d ?label ?tree ?entry WHERE {{
      VALUES ?d {{ {values} }}
      ?d rdfs:label ?label .
      OPTIONAL {{ ?d meshv:treeNumber ?tree }}
      OPTIONAL {{
        {{ ?d meshv:preferredConcept ?c }} UNION {{ ?d meshv:concept ?c }}
        ?c meshv:term ?t . ?t meshv:prefLabel ?entry
      }}
    }}"""
    response = session.get(
        SPARQL, params={"query": query, "format": "JSON", "limit": 100000}, timeout=120
    )
    response.raise_for_status()
    return response.json()["results"]["bindings"]  # type: ignore[no-any-return]


def main() -> None:
    session = requests.Session()
    session.headers["User-Agent"] = (
        "pyeuropepmc-mesh-snapshot (+https://github.com/JonasHeinickeBio/pyEuropePMC)"
    )
    wanted = wanted_headings()
    ids: dict[str, str] = {}
    missing: list[str] = []
    for label in wanted:
        ui = descriptor_id(session, label)
        if ui:
            ids[ui] = label
        else:
            missing.append(label)
        time.sleep(0.05)
    rows: list[dict[str, dict[str, str]]] = []
    uis = list(ids)
    for start in range(0, len(uis), 40):
        rows += sparql(session, uis[start : start + 40])
    trees: dict[str, set[str]] = {}
    headings: dict[str, str] = {}
    entries: dict[str, dict[str, str]] = {}
    for row in rows:
        ui = row["d"]["value"].rsplit("/", 1)[-1]
        headings[ui] = row["label"]["value"]
        if "tree" in row:
            trees.setdefault(ui, set()).add(row["tree"]["value"].rsplit("/", 1)[-1])
        if "entry" in row:
            term = row["entry"]["value"]
            entries.setdefault(ui, {}).setdefault(term.lower(), term)
    descriptors = []
    for ui in uis:
        if ui not in headings:
            missing.append(ids[ui])
            continue
        heading = headings[ui]
        terms = [t for k, t in entries.get(ui, {}).items() if k != heading.lower()]
        descriptors.append(
            {
                "ui": ui,
                "heading": heading,
                "trees": sorted(trees.get(ui, set())),
                "entry_terms": sorted(terms, key=str.lower),
            }
        )
    snapshot = {
        "source": (
            "NLM MeSH (https://id.nlm.nih.gov/mesh/), as published; "
            "see scripts/build_mesh_snapshot.py"
        ),
        "built": datetime.date.today().isoformat(),
        "descriptors": sorted(descriptors, key=lambda d: str(d["heading"]).lower()),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(descriptors)} descriptors, {OUT.stat().st_size // 1024} KB -> {OUT}")
    if missing:
        print("not found under that exact name:", "; ".join(sorted(set(missing))), file=sys.stderr)


if __name__ == "__main__":
    main()
