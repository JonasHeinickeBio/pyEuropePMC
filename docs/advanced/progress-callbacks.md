# Progress callbacks

`FullTextClient.download_fulltext_batch()` can report progress while it downloads a list of articles: pass a function, and the client calls it with a `ProgressInfo` object. This page shows how to use the callback, lists the `ProgressInfo` fields and explains when the callback runs; `download_fulltext_batch_parallel()`, which shows its own progress bar, is covered at the end.

## Report progress

```python
from pyeuropepmc import FullTextClient, ProgressInfo


def print_progress(progress: ProgressInfo) -> None:
    print(
        f"{progress.progress_percent:5.1f}%  item {progress.current_item}/{progress.total_items}  "
        f"ok={progress.successful_downloads} failed={progress.failed_downloads}  {progress.status}"
    )


with FullTextClient() as client:
    results = client.download_fulltext_batch(
        ["PMC3312970", "PMC3258128"],
        format_type="xml",
        output_dir="downloads",
        progress_callback=print_progress,
        progress_update_interval=0,
    )

for pmcid, path in results.items():
    print(pmcid, path)  # path is None if the download failed
```

With two successful downloads, the callback prints:

```text
  0.0%  item 0/2  ok=0 failed=0  initialized
 50.0%  item 1/2  ok=0 failed=0  downloading PMCPMC3312970
100.0%  item 2/2  ok=1 failed=0  downloading PMCPMC3258128
100.0%  item 2/2  ok=2 failed=0  completed
```

`download_fulltext_batch()` parameters:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `pmcids` | `list[str]` | required | PMC IDs, with or without the `PMC` prefix. |
| `format_type` | `str` | `"pdf"` | `"pdf"`, `"xml"` or `"html"`. |
| `output_dir` | `str`, `Path` or `None` | `None` | Target directory, created if needed; `None` means the current directory. Files are named `PMC<id>.<format>`. |
| `skip_errors` | `bool` | `True` | With `False`, a `FullTextError` raised by a download is re-raised instead of being recorded as `None`. |
| `progress_callback` | callable or `None` | `None` | Called with a `ProgressInfo`; the return value is ignored. |
| `progress_update_interval` | `float` | `1.0` | Minimum number of seconds between the per-item calls. |

It returns a dict that maps each ID, as you passed it, to the `Path` of the downloaded file, or to `None` if the download failed. Files already in the [download cache](../features/caching/README.md#fulltextclient-download-cache) are copied instead of downloaded.

## When the callback runs

1. Once before the first download, with `status="initialized"` and `current_item=0`.
2. Before each download, if at least `progress_update_interval` seconds have passed since the previous call. `status` is `"downloading PMC"` followed by the ID as you passed it. The counters describe the downloads finished so far, while `current_item` and `progress_percent` already include the item that is about to start.
3. Once after the last download, with `status="completed"`.

With the default interval of 1.0 second and fast downloads (for example, files served from the cache), only the first and the last call may happen. After each download the client also sets `status` to `"completed PMC…"`, `"failed PMC…"` or `"error PMC…: …"`, but the next call overwrites it first, so the callback never sees these values; use `successful_downloads` and `failed_downloads` instead.

> **Known limitation.** The per-item status adds a `PMC` prefix to the ID as given, so `"PMC3312970"` appears as `downloading PMCPMC3312970`. Use `current_pmcid` if you display the ID.

## ProgressInfo

`ProgressInfo` is importable from `pyeuropepmc`. The client creates it; if you create one yourself, only `total_items` is required, `status` defaults to `"starting"`, `format_type` to `"unknown"` and `start_time` to the current time.

| Attribute | Type | Meaning |
|---|---|---|
| `total_items` | `int` | Number of IDs in the batch. |
| `current_item` | `int` | 1-based position of the item being processed; `0` before the first. |
| `current_pmcid` | `str` or `None` | The ID being processed, as passed in. |
| `status` | `str` | See [When the callback runs](#when-the-callback-runs). |
| `successful_downloads` | `int` | Downloads that produced a file. |
| `failed_downloads` | `int` | Downloads that returned `None` or raised `FullTextError`. |
| `cache_hits` | `int` | Items whose file was already valid in the download cache. |
| `format_type` | `str` | The batch format. |
| `start_time` | `float` | Unix time when the batch started. |
| `current_file_size` | `int` | Size in bytes of the last downloaded file. |
| `total_downloaded_bytes` | `int` | Sum of the sizes of the downloaded files. |

| Property | Type | Meaning |
|---|---|---|
| `progress_percent` | `float` | `current_item / total_items * 100`, or `0.0` for an empty batch. |
| `elapsed_time` | `float` | Seconds since `start_time`. |
| `estimated_total_time` | `float` or `None` | `elapsed_time / current_item * total_items`; `None` before the first item. |
| `estimated_remaining_time` | `float` or `None` | `estimated_total_time - elapsed_time`, at least 0; `None` before the first item. |
| `completion_rate` | `float` | Items per second, `current_item / elapsed_time`. |

`to_dict()` returns the attributes except `start_time`, plus `progress_percent`, `elapsed_time`, `estimated_remaining_time` and `completion_rate`. `str(progress)` gives a one-line summary.

## Progress bar with tqdm

tqdm is installed with pyEuropePMC. This bar counts finished downloads; the final `"completed"` call brings it to the total.

```python
from tqdm import tqdm

from pyeuropepmc import FullTextClient, ProgressInfo

pmcids = ["PMC3312970", "PMC3258128"]

with FullTextClient() as client, tqdm(total=len(pmcids), unit="article") as bar:

    def update_bar(progress: ProgressInfo) -> None:
        bar.n = progress.successful_downloads + progress.failed_downloads
        bar.set_postfix(ok=progress.successful_downloads, failed=progress.failed_downloads)
        bar.refresh()

    client.download_fulltext_batch(
        pmcids,
        format_type="xml",
        output_dir="downloads",
        progress_callback=update_bar,
        progress_update_interval=0.5,
    )
```

## Parallel downloads

`download_fulltext_batch_parallel()` downloads with several worker threads, each limited to one request per second, and shows a tqdm progress bar. It has no `progress_callback` parameter.

```python
from pyeuropepmc import FullTextClient

with FullTextClient() as client:
    results = client.download_fulltext_batch_parallel(
        ["PMC3312970", "PMC3258128"],
        format_type="xml",
        output_dir="downloads",
        max_workers=2,
    )
    print(sum(path is not None for path in results.values()), "files")
    print(sorted(client.download_stats))
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `pmcids` | `list[str]` | required | PMC IDs, with or without the `PMC` prefix. |
| `format_type` | `str` | `"pdf"` | `"pdf"`, `"xml"` or `"html"`. |
| `output_dir` | `str`, `Path` or `None` | `None` | Target directory; `None` means the current directory. |
| `skip_errors` | `bool` | `True` | Continue after a failed download. |
| `max_workers` | `int` or `None` | `None` | `None` means `min(os.cpu_count(), 8)`; other values are clamped to 1-8. |
| `show_progress` | `bool` | `True` | Show a tqdm progress bar. |
| `verbose` | `bool` | `False` | More detailed logging. |

The return value has the same shape as for `download_fulltext_batch()`. Afterwards, `client.download_stats` holds `total_items`, `format_type`, `max_workers`, `start_time`, `end_time`, `total_time_seconds`, `avg_speed`, `success_rate`, per-worker counts in `worker_stats` and totals in `global_stats`.

## Example script

[`examples/07-advanced-parsing/02-progress-callbacks.py`](https://github.com/JonasHeinickeBio/pyEuropePMC/blob/main/examples/07-advanced-parsing/02-progress-callbacks.py) shows several callback styles, including a tqdm bar.

## Related pages

- [Full-text retrieval](../features/fulltext/README.md)
- [Caching](../features/caching/README.md)
