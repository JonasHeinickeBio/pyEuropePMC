# ORCID Integration

Look up researcher profiles and publications from the ORCID public registry.

## Basic Usage

```python
from pyeuropepmc.enrichment import OrcidClient

client = OrcidClient()

# Get researcher profile
profile = client.get_profile("0000-0002-1825-0097")
print(f"Name: {profile.get('name', {}).get('given-names', {}).get('value')} "
      f"{profile.get('name', {}).get('family-name', {}).get('value')}")
print(f"Works: {len(profile.get('activities-summary', {}).get('works', {}).get('group', []))}")
```

## Get Publications

```python
works = client.get_works("0000-0002-1825-0097")
for work in works:
    title = work.get("title", {}).get("title", {}).get("value", "Unknown")
    print(f"  {title}")
```

## ID Normalization

The client automatically normalizes ORCID identifiers:

```python
# All of these work:
client.get_profile("0000-0002-1825-0097")
client.get_profile("https://orcid.org/0000-0002-1825-0097")
client.get_profile("orcid.org/0000-0002-1825-0097")
```

## Enrichment

The `OrcidClient` also supports the enrichment interface:

```python
result = client.enrich("0000-0002-1825-0097")
if result:
    print(f"Found {len(result.get('works', []))} works")
```

## Free API

The ORCID Public API requires no authentication for public records. Rate limits are generous.

## Features

- ✅ Public API — no auth needed
- ✅ Automatic ORCID ID normalization
- ✅ Profile lookup (name, biography, employment, education)
- ✅ Works/publications retrieval
- ✅ Standard enrichment client interface
