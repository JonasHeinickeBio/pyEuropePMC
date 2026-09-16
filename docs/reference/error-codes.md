# Error codes

Every exception pyEuropePMC raises carries an error code, such as `NET001` or `QUERY003`. This page explains how to read an error and lists every code in `pyeuropepmc.core.error_codes.ErrorCodes`: what it means, where the library raises it, and what usually fixes it.

## Read an error

```python
from pyeuropepmc import QueryBuilder
from pyeuropepmc.core.exceptions import PyEuropePMCError

try:
    QueryBuilder().and_()
except PyEuropePMCError as err:
    print(err.error_code.value)  # QUERY003
    print(err.context)  # {'operator': 'AND'}
    print(err.is_retryable())  # False
    print(err.get_recovery_options())
```

| Attribute or method | What it gives |
|---|---|
| `str(err)` | `[CODE] message` |
| `err.error_code` | The `ErrorCodes` member; `.value` is the code as a string |
| `err.context` | A dict with details, such as the query, the PMCID or the HTTP status |
| `err.status_code` | The HTTP status, when there is one |
| `err.is_retryable()` | `True` for `NET`, `RATE`, `RETRY` and `HTTP5xx` codes and for `HTTP408` and `HTTP429` |
| `err.get_recovery_options()` | Short suggestions for this code |
| `err.__cause__` | The original exception, when pyEuropePMC wrapped another error |

The messages of the `HTTP` codes, and any message built with `get_error_message(code, include_help_link=True)`, end with a `Docs:` link to the section of this page that lists the code.

## Exception classes

All exceptions are defined in `pyeuropepmc.core.exceptions` and derive from `PyEuropePMCError`.

| Exception | Raised by | Codes |
|---|---|---|
| `SearchError`, exported as `pyeuropepmc.EuropePMCError` | `SearchClient` | `SEARCH001`–`SEARCH005`, `NET001` |
| `APIClientError` | Requests made by `ArticleClient`, `AnnotationsClient`, `FullTextClient`, the multi-source search clients and the enrichment clients | `NET001`, `NET002`, `HTTP…`, `AUTH401`, `RATE429`, `RETRY001`, `API001`, `FULL007`, `GENERIC002` |
| `FullTextError` | `FullTextClient`, `FTPDownloader` | `FULL001`–`FULL011` |
| `ParsingError` | `FullTextXMLParser`, `EuropePMCParser`, `SearchClient.search_and_parse()` | `PARSE001`–`PARSE004` |
| `QueryBuilderError` | `QueryBuilder` | `QUERY001`–`QUERY004`, `CONFIG003` |
| `ValidationError` | `ArticleClient` and `AnnotationsClient` argument checks; the JSON helpers in `pyeuropepmc.utils.helpers` | `VALID001`, `VALID002`, `VALID004`–`VALID007` |
| `ConfigurationError` | `CacheConfig` and the disk cache | `CONFIG001` |
| `UnpaywallError` | `UnpaywallClient` | `VALID002`, `VALID003`, `NET001` |

`RateLimitError`, `ClientError`, `APIError`, `FileError` and `ModelError` are defined, but the current code does not raise them.

## How SearchClient reports failed requests

- `search()` checks the query, the page size and the format before sending anything, and raises `SEARCH001`, `SEARCH002` or `SEARCH004`.
- A failed request, whether a network error, a timeout or an HTTP error status, is raised as `SearchError` with code `NET001`. The `APIClientError` it wraps is in `err.__cause__`. Its code is `HTTP403`, `HTTP404`, `HTTP500` or `RATE429` for those statuses, `FULL007` for a closed client, and `NET001` for anything else.
- `search_all()` and `fetch_all_pages()` do not raise when a request fails: they stop and return the records collected so far. `search_ids_only()` returns an empty list on any error.

## Network: NET

| Code | Meaning | Raised by | Typical fix |
|---|---|---|---|
| `NET001` | A request failed: no connection, a timeout, or an HTTP status without a more specific code | Every client's requests. `SearchClient` and `ArticleClient` also use it to wrap a failed request, and `UnpaywallClient` uses it for network errors | Read `err.__cause__` for the HTTP status; check the connection and proxy; retry later |
| `NET002` | A request timed out | Multi-source search clients | Retry, or pass a larger `timeout` to `UnifiedSearch` |
| `NET003` | DNS lookup failed | Not raised by the current code | Check DNS settings |
| `NET004` | The server refused the connection | Not raised | Check the service status and firewall |
| `NET005` | SSL/TLS error | Not raised | Check certificates and proxy settings |
| `NET006` | Connection pool exhausted | Not raised | Send fewer concurrent requests |
| `NET007` | Connection interrupted during transfer | Not raised | Retry |

## HTTP status: HTTP

| Code | Meaning | Raised by | Typical fix |
|---|---|---|---|
| `HTTP400` | Bad request | Multi-source search clients | Simplify the query for that source |
| `HTTP401` | Unauthorised | Not raised; a 401 response uses `AUTH401` | See `AUTH401` |
| `HTTP403` | Access forbidden | Requests by `ArticleClient` and `FullTextClient`; multi-source search clients | Check the identifier; not all content is open |
| `HTTP404` | Not found | Requests by `ArticleClient` and `FullTextClient`, for example `get_fulltext_content()` for an article without full-text XML | Check the ID; call `check_fulltext_availability()` first |
| `HTTP405`, `HTTP406`, `HTTP410`, `HTTP415`, `HTTP416` | The HTTP status with that number | Multi-source search clients | Report a bug: the library builds these requests |
| `HTTP407` | Proxy authentication required | Multi-source search clients | Put the proxy credentials in `HTTPS_PROXY` |
| `HTTP408` | Request timeout | Multi-source search clients | Retry |
| `HTTP413`, `HTTP414` | Request or URL too long | Multi-source search clients | Shorten the query or ask for fewer results |
| `HTTP429` | Too many requests | Not raised; a 429 response uses `RATE429` | See `RATE429` |
| `HTTP500` | Internal server error | Requests by `ArticleClient` and `FullTextClient`; multi-source search clients | Retry later |
| `HTTP501`, `HTTP502`, `HTTP503`, `HTTP504` | Server-side errors | Multi-source search clients | Retry later |

## Authentication and rate limits: AUTH, RATE, RETRY

| Code | Meaning | Raised by | Typical fix |
|---|---|---|---|
| `AUTH401` | The service rejected the credentials | Multi-source search clients | Europe PMC needs no key. For a source that needs one, pass `UnifiedSearch(credentials={"api_key": ...})` or set its variable, such as `CORE_API_KEY` |
| `AUTH403` | The credentials lack permission | Not raised | Check the key's permissions |
| `RATE429` | Rate limit exceeded | Requests by `ArticleClient`, `FullTextClient` and `SearchClient` (in `err.__cause__`); multi-source search clients | Increase `rate_limit_delay`, send fewer requests, retry later |
| `RETRY001` | Retries exhausted | Multi-source search clients | Retry later; raise `rate_limit_delay` or lower `max_workers` in `UnifiedSearch` |
| `RETRY002` | Invalid `Retry-After` header | Not raised | Wait and retry |

## Search: SEARCH

| Code | Meaning | Raised by | Typical fix |
|---|---|---|---|
| `SEARCH001` | Invalid query | `search()` and `get_hit_count()` when `SearchClient.validate_query()` fails: the query is empty, shorter than two characters, has an odd number of `"`, or is more than 30% special characters | Fix the query |
| `SEARCH002` | Page size out of range | `pageSize` or `page_size` outside 1–1000 | Use 1–1000; use `search_all()` for more records |
| `SEARCH003` | Unexpected response or error | A JSON response that cannot be decoded; `get_hit_count()` with a non-JSON `format`; unexpected errors in `search()`, `search_post()` and `get_hit_count()` | Do not pass `format` to `get_hit_count()`; retry |
| `SEARCH004` | Invalid format | `search()` (allowed: `json`, `xml`, `dc`, `lite`, `idlist`) and `search_and_parse()` (allowed: `json`, `xml`, `dc`) | Use an allowed value |
| `SEARCH005` | Results could not be parsed | `search_and_parse()` | Retry, or use `format="json"` |
| `SEARCH006` | Search endpoint not found | Defined for a 404 from the search endpoint, but failed requests currently arrive as `NET001` | See `NET001` |
| `SEARCH007`, `SEARCH008`, `SEARCH009`, `SEARCH010` | No results; invalid parameter; query too long; search rate limited | Not raised | — |

## Full text: FULL

| Code | Meaning | Raised by | Typical fix |
|---|---|---|---|
| `FULL001` | Empty PMCID | `FullTextClient` methods; also wraps unexpected errors in parallel batch downloads | Pass a PMCID |
| `FULL002` | Invalid PMCID | `FullTextClient` methods | Use `PMC` followed by digits, such as `PMC3258128`, or the digits alone |
| `FULL003` | Content not found | `download_xml_by_pmcid()` when every download route fails; `download_xml_by_pmcid_bulk()`; PDF downloads that get a 404 | Check `check_fulltext_availability()`; not every article has full text |
| `FULL004` | Invalid format | `get_fulltext_content()` (allowed: `xml`, `html`); `search_and_download_fulltext()` | Use an allowed format |
| `FULL005` | Download failed | PDF downloads with an HTTP error other than 403 or 404; `FTPDownloader` directory listing, download and ZIP extraction | Retry; check the connection |
| `FULL006` | PDF validation failed | Not raised | — |
| `FULL007` | The client is closed | Any request after `close()` or after the client's `with` block has ended | Create a new client, or keep calls inside the `with` block |
| `FULL008` | Access denied | PDF downloads that get a 403 | The article is not open access; try the XML or another source |
| `FULL009` | A downloaded file could not be written | Saving XML or HTML downloads | Check the output path, permissions and free space |
| `FULL010` | Unsupported batch format | `download_fulltext_batch()` and `download_fulltext_batch_parallel()` (allowed: `pdf`, `xml`, `html`) | Use an allowed format |
| `FULL011` | No URL for this format | Building a full-text URL for a format other than `xml` | Use the `download_*` method for that format |
| `FULL012`–`FULL016` | Unpaywall error; DOI not in Unpaywall; content embargoed; invalid page range; version not available | Not raised | — |

## Parsing: PARSE

| Code | Meaning | Raised by | Typical fix |
|---|---|---|---|
| `PARSE001` | Data is not valid JSON, or has the wrong type | `search_and_parse()` when a JSON response is not a dict; `EuropePMCParser.parse_json()`; the `QueryBuilder` field-list lookup | Check the input |
| `PARSE002` | XML could not be parsed | `FullTextXMLParser` on malformed XML; `EuropePMCParser.parse_xml()` and `parse_dc()` | Check that the XML is complete |
| `PARSE003` | No content to parse, or the wrong type | `FullTextXMLParser` methods called before XML was loaded; `FullTextXMLParser` given `None`, an empty string or `bytes`; `EuropePMCParser` given empty input | Pass a non-empty string to `FullTextXMLParser(xml)`; decode `bytes` first |
| `PARSE004` | Unsupported format or structure | `search_and_parse()` when the response does not match `format`; `EuropePMCParser.parse_xml()` without result elements | Use a matching `format` |
| `PARSE005` | The document declares an XML entity and was refused | Every entry point that parses XML: full text, search responses, the JATS normalizer, figure extraction, the bioRxiv manifest, benchmark metrics | Remove the `<!ENTITY>` declaration, or fetch the document from a source that does not use one |

## Validation: VALID

| Code | Meaning | Raised by | Typical fix |
|---|---|---|---|
| `VALID001` | Invalid argument; the message text about dictionaries is generic | `ArticleClient` checks of the source, ID, `result_type`, `format`, `page`, `page_size` and `callback`; `AnnotationsClient` argument checks; `deep_merge_dicts()` | For `ArticleClient`, `err.context["field_name"]` names the argument |
| `VALID002` | Invalid value | `save_to_json()` and `load_json()` permission errors; `UnpaywallClient` without a valid email | Check the file path; pass `email=` to `UnpaywallClient` |
| `VALID003` | Required value missing | `UnpaywallClient.lookup_by_doi()` with an empty DOI | Pass a DOI |
| `VALID004` | JSON file not found or unreadable | `load_json()` | Check the path and the file encoding |
| `VALID005` | Invalid JSON in a file | `load_json()` | Fix the file |
| `VALID006` | JSON file could not be written | `save_to_json()` | Check permissions and free space |
| `VALID007` | Data cannot be serialised to JSON | `save_to_json()` | Convert sets, dates and other objects first |

## Configuration: CONFIG

| Code | Meaning | Raised by | Typical fix |
|---|---|---|---|
| `CONFIG001` | Invalid configuration | `CacheConfig` with `ttl` below 0, `size_limit_mb` below 1 or `namespace_version` below 1; a disk cache whose schema cannot be migrated | Fix the value; see [Caching](../features/caching/README.md) |
| `CONFIG002` | Invalid configuration value | Not raised | — |
| `CONFIG003` | A required package is missing | `QueryBuilder.save()`, `from_file()`, `from_string()`, `translate()`, `to_query_object()` and `evaluate()` when `search-query` cannot be imported | `search-query` is a base dependency: reinstall pyeuropepmc |

`QueryBuilder(validate=True)` is the exception: it checks for `search-query` in the constructor, warns and continues with validation off rather than raising `CONFIG003` later.

## Query builder: QUERY

| Code | Meaning | Raised by | Typical fix |
|---|---|---|---|
| `QUERY001` | Empty or invalid term or field | `keyword()`, `field()`, `pmcid()`, `source()`, `accession_type()`, `cites()`, `raw()`, `group()` or `from_string()` given an empty or unknown value; `build()` on an empty builder | Pass a value and a known field name |
| `QUERY002` | Invalid range | `date_range()` with an invalid year or date, or a start after the end; `citation_count()` with a negative count or a minimum above the maximum | Fix the range |
| `QUERY003` | Operator in the wrong place | `and_()`, `or_()` or `not_()` where no operator is allowed, for example before the first term; `build()` when the query ends with an operator | Put operators between terms |
| `QUERY004` | Validation or conversion failed | `build()` on `QueryBuilder(validate=True)`, which rejects range filters such as `PUB_YEAR:[2020 TO 2023]`; failures in `save()`, `from_file()`, `from_string()` and `translate()`, such as an unsupported platform | Read the reason after "Query validation failed:" |

## Unpaywall: UNPAY

| Code | Meaning | Raised by | Typical fix |
|---|---|---|---|
| `UNPAY001`, `UNPAY002` | Unpaywall lookup failed; invalid DOI | Not raised; `UnpaywallClient` uses `NET001`, `VALID002` and `VALID003` | — |

## Fallback codes: GENERIC

These codes are used when an exception is raised with a message but no code. The message carries the details.

| Code | Exception |
|---|---|
| `GENERIC001` | `PyEuropePMCError` and classes without their own fallback, such as `QueryBuilderError` and `UnpaywallError` |
| `GENERIC002` | `APIClientError`, for example an HTTP error reported by an enrichment client |
| `GENERIC003` | `SearchError` |
| `GENERIC004` | `FullTextError` |
| `GENERIC005` | `ParsingError` |
| `GENERIC006` | `ValidationError` |
| `GENERIC007` | `ConfigurationError` |

## Other codes: API, CLIENT, FILE, MODEL, AVAIL, LICENSE

| Code | Meaning | Raised by |
|---|---|---|
| `API001` | An HTTP status without a specific code | Multi-source search clients; read `err.status_code` |
| `API002`, `API003`, `API004` | Malformed response; rate-limit warning; endpoint not available | Not raised |
| `CLIENT001`, `CLIENT002`, `CLIENT003` | Client set-up failed; session expired; credentials missing | Not raised |
| `FILE001`–`FILE004` | File not found; permission denied; empty or corrupt file; operation interrupted | Not raised |
| `MODEL001`–`MODEL005` | Invalid model data; validation failed; conversion failed; attribute missing; type mismatch | Not raised |
| `AVAIL001`, `AVAIL002`, `AVAIL003` | Content not available; full text not available; access restricted | Not raised |
| `LICENSE001`, `LICENSE002` | The licence does not allow the action; licence information unavailable | Not raised |
