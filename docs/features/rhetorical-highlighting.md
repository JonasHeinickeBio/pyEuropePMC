# Rhetorical highlighting

`RhetoricalHighlighter` splits text into sentences and labels each sentence with a rhetorical role such as method, result or limitation. The default classifier is a set of keyword rules that runs offline with no API key; you can plug in a language model to classify the sentences the rules do not match.

## Classify text

```python
from pyeuropepmc.features.fulltext import RhetoricalHighlighter

text = """
We conducted a randomized controlled trial of 500 patients with chronic fatigue syndrome.
Our results show a significant improvement in fatigue scores after 12 weeks of treatment.
This study was limited by the short follow-up period.
These findings suggest that cognitive behavioral therapy is effective for ME/CFS.
"""

highlighter = RhetoricalHighlighter()
doc = highlighter.highlight(text)

for sentence in doc.sentences:
    print(f"[{sentence.role.value:12s}] {sentence.confidence:.2f} {sentence.text}")
```

Output:

```text
[method      ] 0.50 We conducted a randomized controlled trial of 500 patients with chronic fatigue syndrome.
[result      ] 0.50 Our results show a significant improvement in fatigue scores after 12 weeks of treatment.
[unknown     ] 0.00 This study was limited by the short follow-up period.
[claim       ] 0.60 These findings suggest that cognitive behavioral therapy is effective for ME/CFS.
```

The third sentence is `unknown` because no rule matches it: the limitation rule looks for words such as "limitation", "limited to" and "caveat", not "limited by".

`highlight_text()` does the same in one call:

```python
from pyeuropepmc.features.fulltext import highlight_text

doc = highlight_text(
    "Previous studies have linked fatigue to immune activation. "
    "We used a cohort of 120 patients. "
    "In contrast to earlier reports, IL-6 was unchanged. "
    "A limitation is the small sample.",
    title="Demo",
)
print([(s.role.value, s.confidence) for s in doc.sentences])
```

Output:

```text
[('background', 0.5), ('method', 0.5), ('contradicting_citation', 0.4), ('limitation', 0.6)]
```

## How sentences are classified

1. The text is stripped and split into sentences after every `.`, `!` or `?` that is followed by whitespace. Abbreviations such as "et al." or "e.g." therefore end a sentence too.
2. Each sentence is matched against nine groups of regular expressions, one group per role. Every group has a fixed confidence, and the matching group with the highest confidence wins; on a tie, the group listed first in the table below wins.
3. A sentence whose best confidence is below `confidence_threshold` (default 0.3) is labelled `unknown`.
4. Only if `use_llm=True` and an `llm_client` is given: a sentence whose rule confidence is below 0.4 is sent to the model. Every rule has a confidence of at least 0.4, so in practice only sentences that match no rule reach the model. The model's answer replaces the rule result when its confidence is higher.

## Roles

`RhetoricalRole` is a string enum with eleven members. The rule confidence is the value a sentence receives when that rule group matches.

| Role (`.value`) | Rule confidence | Examples of trigger phrases |
|---|---|---|
| `claim` | 0.6 | "we show", "we demonstrate", "these findings suggest", "importantly" |
| `method` | 0.5 | "we used", "we conducted", "using", "dataset", "protocol" |
| `result` | 0.5 | "we observed", "our results", "resulted in", "increased by" |
| `limitation` | 0.6 | "limitation", "caveat", "limited to", "potential bias" |
| `conclusion` | 0.5 | "in conclusion", "taken together", "future work" |
| `background` | 0.5 | "previous studies", "related work", "it is well known" |
| `motivation` | 0.5 | "we aim to", "the challenge of", "however", "gap in" |
| `supporting_citation` | 0.4 | "consistent with", "in agreement with", "according to" |
| `contradicting_citation` | 0.4 | "in contrast", "contrary to", "unlike" |
| `supplementary` | no rule | assigned only by a language model |
| `unknown` | 0.0 | no rule matched, or confidence below the threshold |

`RhetoricalRole.display_labels()` returns the display label for each role (used by `summary()`), and `RhetoricalRole.hex_colors()` returns a colour per role.

## Work with the result

`highlight()` returns a `HighlightedDocument` whose statistics are already computed.

```python
from pyeuropepmc.features.fulltext import RhetoricalHighlighter

doc = RhetoricalHighlighter().highlight(
    "We used a cohort of 120 patients. We observed that cytokine levels increased by 30%. "
    "A limitation is the small sample."
)

for role, sentences in doc.group_by_role().items():
    print(role, [s.text for s in sentences])

stats = doc.compute_statistics()
print(stats["total_sentences"], stats["role_counts"])
print(doc.summary())
```

Output:

```text
method ['We used a cohort of 120 patients.']
result ['We observed that cytokine levels increased by 30%.']
limitation ['A limitation is the small sample.']
3 {'method': 1, 'result': 1, 'limitation': 1}
Title: N/A
Sentences: 3
  🟢 Method: 1 (33.3%)
  🟡 Result: 1 (33.3%)
  🔴 Limitation: 1 (33.3%)
```

`HighlightedDocument`:

| Member | Type | Description |
|---|---|---|
| `sentences` | `list[SentenceAnnotation]` | Sentences in document order |
| `title`, `authors`, `source` | `str` | Values passed to `highlight()`; default `""` |
| `statistics` | `dict` | Filled by `compute_statistics()`; `highlight()` calls it for you |
| `group_by_role()` | `dict[str, list[SentenceAnnotation]]` | Keys are role values (`"method"`), in order of first appearance |
| `compute_statistics()` | `dict` | Keys `total_sentences`, `role_counts`, `role_percentages`, `mean_confidence_per_role`, `overall_mean_confidence`; also stored on `statistics` |
| `summary()` | `str` | A title line, a sentence count, then one line per role with count and percentage, most frequent first |
| `to_dict()`, `to_json(indent=2)` | `dict`, `str` | Keys `title`, `authors`, `source`, `sentences`, `statistics` |

`SentenceAnnotation`:

| Field | Type | Default | Description |
|---|---|---|---|
| `text` | `str` | required | The sentence |
| `role` | `RhetoricalRole` | `RhetoricalRole.UNKNOWN` | Assigned role |
| `confidence` | `float` | `0.0` | Confidence of the winning rule or model answer |
| `start_char`, `end_char` | `int` | `0` | Offsets into the stripped input, counting one separator character between sentences; they drift where sentences are separated by more than one whitespace character |
| `explanation` | `str` | `""` | Not filled in by `highlight()`, including when a model is used |
| `metadata` | `dict` | `{}` | Not filled in by `highlight()` |

## Parameters

`RhetoricalHighlighter(use_llm=False, llm_client=None, llm_model="gpt-4o-mini", confidence_threshold=0.3)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `use_llm` | `bool` | `False` | Send unmatched sentences to `llm_client` |
| `llm_client` | object with a `chat()` method | `None` | See [Use a language model](#use-a-language-model) |
| `llm_model` | `str` | `"gpt-4o-mini"` | Passed to `llm_client.chat()` as `model` |
| `confidence_threshold` | `float` | `0.3` | Sentences below this confidence become `unknown` |

`highlight(text, title="", authors="", source="")` returns a `HighlightedDocument`.

The module-level helpers create a highlighter with default settings:

| Function | Returns |
|---|---|
| `highlight_text(text, use_llm=False, llm_client=None, title="", authors="")` | `HighlightedDocument` |
| `highlight_pdf_text(pdf_path, use_llm=False, llm_client=None, title="", authors="")` | `HighlightedDocument`, or `None` when no text could be extracted |

## Use a language model

The highlighter calls `llm_client.chat(messages=[{"role": "user", "content": prompt}], model=llm_model, temperature=0.0)` and expects a JSON string such as `{"role": "background", "confidence": 0.9, "explanation": "..."}`. No client in pyeuropepmc implements this method, so write a small adapter around the model API you use. A reply that is not valid JSON, or names an unknown role, counts as `unknown` with confidence 0.0; an exception raised by `chat()` is logged and the rule result is kept.

```python
import json

from pyeuropepmc.features.fulltext import RhetoricalHighlighter


class ChatAdapter:
    """Adapter with the chat() signature the highlighter calls."""

    def chat(self, messages, model, temperature):
        # Replace this with a call to your model; return its JSON reply as a string.
        return json.dumps({"role": "background", "confidence": 0.9, "explanation": "stub"})


highlighter = RhetoricalHighlighter(use_llm=True, llm_client=ChatAdapter())
doc = highlighter.highlight("The sky was grey. We used a cohort.")
print([(s.role.value, s.confidence) for s in doc.sentences])
```

Output:

```text
[('background', 0.9), ('method', 0.5)]
```

The second sentence matches the method rule, so it never reaches the model.

## Text from PDF files

`highlight_pdf_text()` extracts the text with the first available library among PyMuPDF (`import fitz`), pdfplumber and pdfminer.six, then calls `highlight()` with the file path as `source`. None of these libraries is installed with pyeuropepmc; install one yourself, for example `pip install pymupdf`. If none is installed, or extraction fails for another reason such as a missing file, the function logs "No PDF extraction library available" and returns `None`.

```python
from pyeuropepmc.features.fulltext import highlight_pdf_text

doc = highlight_pdf_text("paper.pdf")
if doc is None:
    print("No text extracted")
else:
    print(doc.summary())
```

## Known limitations

- The rules match keywords, not meaning. Many sentences come back `unknown`, and a sentence that contains a trigger word in another sense (for example "using") is labelled by that word.
- The splitter ends a sentence at abbreviations such as "et al." and "e.g.".
- `supplementary` is never assigned without a language model.
