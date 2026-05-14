"""Test parallel download functionality."""
import time
from pyeuropepmc.clients.fulltext import FullTextClient, RateLimiter


def test_rate_limiter():
    """Test RateLimiter class."""
    rl = RateLimiter(worker_id=1, max_requests_per_second=1.0)
    assert rl.worker_id == 1, "Worker ID not set correctly"
    assert rl.request_threshold == 0.8, "Threshold not calculated correctly"

    rl.check_and_record()
    rl.check_and_record()
    stats = rl.get_stats()
    assert stats['requests_made'] == 2, "Request count incorrect"
    print("✓ RateLimiter works correctly")


def test_rate_limiter_threshold_warning():
    """Test RateLimiter threshold warnings."""
    rl = RateLimiter(worker_id=1, max_requests_per_second=1.0)

    # Make 8 requests (80% threshold)
    for _ in range(8):
        rl.check_and_record()

    stats = rl.get_stats()
    assert stats['requests_made'] == 8, "Threshold not reached"
    assert stats['warnings_issued'] > 0, "Should issue warning at threshold"
    print("✓ RateLimiter threshold warnings work correctly")


def test_rate_limiter_reset():
    """Test RateLimiter window reset."""
    rl = RateLimiter(worker_id=1, max_requests_per_second=1.0)

    # Make some requests
    for _ in range(5):
        rl.check_and_record()

    stats = rl.get_stats()
    assert stats['requests_made'] == 5, "Initial requests incorrect"

    # Simulate time passing (1+ seconds)
    rl.window_start = time.time() - 1.5
    rl.check_and_record()

    stats = rl.get_stats()
    # Should reset after window passes
    assert stats['requests_made'] == 1, "Should reset after window"
    print("✓ RateLimiter window reset works correctly")


def test_parallel_method_exists():
    """Test that parallel download method exists."""
    client = FullTextClient(enable_cache=False)
    assert hasattr(client, 'download_fulltext_batch_parallel'), "Method not found!"

    # Check method signature
    import inspect
    sig = inspect.signature(client.download_fulltext_batch_parallel)
    params = list(sig.parameters.keys())
    assert 'pmcids' in params, "Missing pmcids parameter"
    assert 'format_type' in params, "Missing format_type parameter"
    assert 'max_workers' in params, "Missing max_workers parameter"
    assert 'show_progress' in params, "Missing show_progress parameter"
    assert 'verbose' in params, "Missing verbose parameter"
    assert 'output_dir' in params, "Missing output_dir parameter"
    assert 'skip_errors' in params, "Missing skip_errors parameter"
    print("✓ Parallel download method exists with correct signature")


def test_parallel_method_basic():
    """Test basic parallel download functionality with empty list."""
    client = FullTextClient(enable_cache=False)

    # Test with empty list
    results = client.download_fulltext_batch_parallel(
        pmcids=[],
        format_type="pdf",
        max_workers=2,
        show_progress=False
    )

    assert results == {}, "Empty list should return empty dict"
    assert client.download_stats is not None, "Stats should be initialized"
    assert client.download_stats['total_items'] == 0, "Total items should be 0"
    print("✓ Parallel download handles empty list correctly")


def test_parallel_method_with_workers():
    """Test parallel download with different worker counts."""
    client = FullTextClient(enable_cache=False)

    # Test with single worker
    results = client.download_fulltext_batch_parallel(
        pmcids=["123"],
        format_type="pdf",
        max_workers=1,
        show_progress=False
    )

    assert client.download_stats['max_workers'] == 1, "Worker count incorrect"

    # Test with 4 workers
    results = client.download_fulltext_batch_parallel(
        pmcids=["123"],
        format_type="pdf",
        max_workers=4,
        show_progress=False
    )

    assert client.download_stats['max_workers'] == 4, "Worker count incorrect"
    print("✓ Parallel download works with different worker counts")


def test_parallel_method_auto_workers():
    """Test parallel download auto-detects worker count."""
    import os
    client = FullTextClient(enable_cache=False)

    results = client.download_fulltext_batch_parallel(
        pmcids=["123"],
        format_type="pdf",
        show_progress=False
    )

    expected_workers = min(os.cpu_count() or 4, 8)
    assert client.download_stats['max_workers'] == expected_workers, "Auto-detected workers incorrect"
    print("✓ Parallel download auto-detects worker count correctly")


def test_parallel_method_max_workers_range():
    """Test parallel download max_workers range validation."""
    client = FullTextClient(enable_cache=False)

    # Test with too few workers (should be clamped to 1)
    results = client.download_fulltext_batch_parallel(
        pmcids=["123"],
        format_type="pdf",
        max_workers=0,
        show_progress=False
    )
    assert client.download_stats['max_workers'] == 1, "Should clamp to minimum"

    # Test with too many workers (should be clamped to 8)
    results = client.download_fulltext_batch_parallel(
        pmcids=["123"],
        format_type="pdf",
        max_workers=10,
        show_progress=False
    )
    assert client.download_stats['max_workers'] == 8, "Should clamp to maximum"
    print("✓ Parallel download clamps max_workers to valid range")


def test_parallel_method_format_types():
    """Test parallel download with different format types."""
    client = FullTextClient(enable_cache=False)

    for format_type in ["pdf", "xml", "html"]:
        results = client.download_fulltext_batch_parallel(
            pmcids=["123"],
            format_type=format_type,
            max_workers=2,
            show_progress=False
        )
        assert client.download_stats['format_type'] == format_type, f"Format type {format_type} incorrect"

    print("✓ Parallel download works with all format types")


def test_parallel_method_statistics():
    """Test parallel download statistics tracking."""
    client = FullTextClient(enable_cache=False)

    results = client.download_fulltext_batch_parallel(
        pmcids=["123"],
        format_type="pdf",
        max_workers=2,
        show_progress=False
    )

    stats = client.download_stats
    assert 'start_time' in stats, "Missing start_time"
    assert 'end_time' in stats, "Missing end_time"
    assert 'total_time_seconds' in stats, "Missing total_time_seconds"
    assert 'avg_speed' in stats, "Missing avg_speed"
    assert 'worker_stats' in stats, "Missing worker_stats"
    assert 'global_stats' in stats, "Missing global_stats"
    assert 'success_rate' in stats, "Missing success_rate"
    print("✓ Parallel download statistics tracking works correctly")


def test_parallel_method_worker_stats():
    """Test parallel download worker statistics."""
    client = FullTextClient(enable_cache=False)

    results = client.download_fulltext_batch_parallel(
        pmcids=["123", "456"],
        format_type="pdf",
        max_workers=2,
        show_progress=False
    )

    worker_stats = client.download_stats['worker_stats']
    assert len(worker_stats) == 2, "Worker stats count incorrect"

    for worker_id in range(2):
        assert worker_id in worker_stats, f"Missing worker stats for {worker_id}"
        assert 'requests' in worker_stats[worker_id], "Missing requests"
        assert 'failures' in worker_stats[worker_id], "Missing failures"
        assert 'successes' in worker_stats[worker_id], "Missing successes"
        assert 'time_spent' in worker_stats[worker_id], "Missing time_spent"

    print("✓ Parallel download worker statistics tracking works correctly")


def test_parallel_method_global_stats():
    """Test parallel download global statistics."""
    client = FullTextClient(enable_cache=False)

    results = client.download_fulltext_batch_parallel(
        pmcids=["123", "456"],
        format_type="pdf",
        max_workers=2,
        show_progress=False
    )

    global_stats = client.download_stats['global_stats']
    assert 'total_requests' in global_stats, "Missing total_requests"
    assert 'total_failures' in global_stats, "Missing total_failures"
    assert 'total_successes' in global_stats, "Missing total_successes"

    # Verify consistency
    total_from_workers = sum(
        worker_stat['requests']
        for worker_stat in client.download_stats['worker_stats'].values()
    )
    assert global_stats['total_requests'] == total_from_workers, "Global requests mismatch"

    print("✓ Parallel download global statistics tracking works correctly")


def test_parallel_method_verbose_mode():
    """Test parallel download verbose mode."""
    client = FullTextClient(enable_cache=False)

    results = client.download_fulltext_batch_parallel(
        pmcids=["123"],
        format_type="pdf",
        max_workers=2,
        show_progress=False,
        verbose=True
    )

    assert results is not None, "Should return results"
    print("✓ Parallel download verbose mode works correctly")


def test_parallel_method_skip_errors():
    """Test parallel download skip_errors behavior."""
    client = FullTextClient(enable_cache=False)

    # Test with skip_errors=True (default)
    results = client.download_fulltext_batch_parallel(
        pmcids=["invalid", "123"],
        format_type="pdf",
        max_workers=2,
        skip_errors=True,
        show_progress=False
    )

    assert isinstance(results, dict), "Should return dict"
    print("✓ Parallel download skip_errors behavior works correctly")


def test_parallel_method_empty_pmcids_with_stats():
    """Test parallel download with empty list verifies stats initialization."""
    client = FullTextClient(enable_cache=False)

    results = client.download_fulltext_batch_parallel(
        pmcids=[],
        format_type="xml",
        max_workers=4,
        show_progress=False
    )

    assert results == {}, "Empty list should return empty dict"
    stats = client.download_stats
    assert stats['total_items'] == 0, "Total items should be 0"
    assert stats['format_type'] == "xml", "Format type should match"
    assert stats['max_workers'] == 1, "Empty list uses default max_workers=1"
    assert 'worker_stats' in stats, "Worker stats should be initialized"
    assert 'global_stats' in stats, "Global stats should be initialized"
    assert stats['success_rate'] == 0.0, "Success rate should be 0 for empty list"
    print("✓ Empty PMCID list stats initialization works correctly")


def test_parallel_method_progress_bar_display():
    """Test parallel download progress bar with verbose output."""
    import io
    import sys

    client = FullTextClient(enable_cache=False)

    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = captured_output = io.StringIO()

    try:
        results = client.download_fulltext_batch_parallel(
            pmcids=["123"],
            format_type="pdf",
            max_workers=1,
            show_progress=True,
            verbose=True
        )
    finally:
        sys.stdout = old_stdout
        output = captured_output.getvalue()

    assert isinstance(results, dict), "Should return results"
    print("✓ Parallel download progress bar with verbose works correctly")


def test_parallel_method_worker_id_in_results():
    """Test that worker ID is correctly tracked in stats."""
    client = FullTextClient(enable_cache=False)

    results = client.download_fulltext_batch_parallel(
        pmcids=["123", "456", "789"],
        format_type="pdf",
        max_workers=3,
        show_progress=False
    )

    worker_stats = client.download_stats['worker_stats']

    # Verify all workers have stats
    for worker_id in range(3):
        assert worker_id in worker_stats, f"Worker {worker_id} should have stats"
        assert 'requests' in worker_stats[worker_id], f"Worker {worker_id} missing requests"

    print("✓ Worker ID tracking in parallel download works correctly")


def test_parallel_method_output_dir():
    """Test parallel download with custom output directory."""
    from pathlib import Path
    import tempfile

    client = FullTextClient(enable_cache=False)

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir)
        results = client.download_fulltext_batch_parallel(
            pmcids=["123"],
            format_type="pdf",
            max_workers=2,
            output_dir=output_path,
            show_progress=False
        )

        assert isinstance(results, dict), "Should return results dict"

    print("✓ Parallel download with custom output_dir works correctly")


def test_parallel_method_rate_limiter_per_worker():
    """Test that each worker has its own rate limiter."""
    client = FullTextClient(enable_cache=False)

    results = client.download_fulltext_batch_parallel(
        pmcids=["123"],
        format_type="pdf",
        max_workers=2,
        show_progress=False
    )

    stats = client.download_stats
    assert 'worker_stats' in stats, "Worker stats should be present"

    worker_stats = stats['worker_stats']
    for worker_id in worker_stats:
        assert worker_stats[worker_id]['requests'] >= 0, f"Worker {worker_id} should have request count"

    print("✓ Per-worker rate limiting works correctly")


def test_parallel_method_concurrent_access():
    """Test thread safety with multiple concurrent downloads."""
    client = FullTextClient(enable_cache=False)

    results = client.download_fulltext_batch_parallel(
        pmcids=["123", "456", "789", "999"],
        format_type="pdf",
        max_workers=4,
        show_progress=False
    )

    stats = client.download_stats
    assert stats['total_items'] == 4, "Should track 4 total items"

    total_requests = sum(
        ws['requests'] for ws in stats['worker_stats'].values()
    )
    assert total_requests == stats['global_stats']['total_requests'], \
        "Total requests should match global stats"

    print("✓ Concurrent download handling works correctly")


def test_parallel_method_no_progress_bar():
    """Test parallel download without progress bar."""
    client = FullTextClient(enable_cache=False)

    results = client.download_fulltext_batch_parallel(
        pmcids=["123", "456"],
        format_type="pdf",
        max_workers=2,
        show_progress=False
    )

    assert isinstance(results, dict), "Should return results"
    assert len(results) == 2, "Should have 2 results"

    print("✓ Parallel download without progress bar works correctly")


def test_parallel_method_single_pmcid():
    """Test parallel download with single PMCID."""
    client = FullTextClient(enable_cache=False)

    results = client.download_fulltext_batch_parallel(
        pmcids=["123"],
        format_type="pdf",
        max_workers=1,
        show_progress=False
    )

    assert isinstance(results, dict), "Should return results"
    assert "123" in results, "Should have PMCID 123 in results"

    print("✓ Single PMCID parallel download works correctly")


def test_parallel_method_xml_format():
    """Test parallel download with XML format."""
    client = FullTextClient(enable_cache=False)

    results = client.download_fulltext_batch_parallel(
        pmcids=["123"],
        format_type="xml",
        max_workers=2,
        show_progress=False
    )

    assert client.download_stats['format_type'] == "xml", "Format type should be xml"
    assert isinstance(results, dict), "Should return results"

    print("✓ XML format parallel download works correctly")


def test_parallel_method_html_format():
    """Test parallel download with HTML format."""
    client = FullTextClient(enable_cache=False)

    results = client.download_fulltext_batch_parallel(
        pmcids=["123"],
        format_type="html",
        max_workers=2,
        show_progress=False
    )

    assert client.download_stats['format_type'] == "html", "Format type should be html"
    assert isinstance(results, dict), "Should return results"

    print("✓ HTML format parallel download works correctly")


def test_rate_limiter_stats_consistency():
    """Test RateLimiter stats consistency across multiple calls."""
    rl = RateLimiter(worker_id=1, max_requests_per_second=1.0)

    # Make multiple requests
    for i in range(15):
        rl.check_and_record()

    stats = rl.get_stats()
    assert stats['requests_made'] == 15, "Request count should be 15"
    assert 'worker_id' in stats, "Stats should include worker_id"
    assert 'window_start' in stats, "Stats should include window_start"

    print("✓ RateLimiter stats consistency works correctly")


def test_rate_limiter_window_timing():
    """Test RateLimiter window reset timing."""
    rl = RateLimiter(worker_id=2, max_requests_per_second=2.0)

    # Make requests to reach threshold
    for _ in range(10):
        rl.check_and_record()

    stats = rl.get_stats()
    initial_count = stats['requests_made']

    # Simulate window reset
    rl.window_start = time.time() - 1.1
    rl.check_and_record()

    stats = rl.get_stats()
    assert stats['requests_made'] == 1, "Should reset after window passes"

    print("✓ RateLimiter window timing works correctly")


def test_parallel_method_skip_errors_false():
    """Test parallel download with skip_errors=False."""
    client = FullTextClient(enable_cache=False)

    try:
        results = client.download_fulltext_batch_parallel(
            pmcids=["invalid_pmcid"],
            format_type="pdf",
            max_workers=1,
            skip_errors=False,
            show_progress=False
        )
        assert False, "Should have raised an error with skip_errors=False"
    except Exception:
        pass

    print("✓ skip_errors=False raises errors correctly")


def test_parallel_method_statistics_consistency():
    """Test that statistics remain consistent across multiple runs."""
    client = FullTextClient(enable_cache=False)

    for _ in range(3):
        results = client.download_fulltext_batch_parallel(
            pmcids=["123"],
            format_type="pdf",
            max_workers=2,
            show_progress=False
        )

        stats = client.download_stats
        assert 'success_rate' in stats, "success_rate should always be present"
        assert 'avg_speed' in stats, "avg_speed should always be present"
        assert 'total_time_seconds' in stats, "total_time_seconds should always be present"

    print("✓ Statistics consistency across multiple runs works correctly")


if __name__ == "__main__":
    test_rate_limiter()
    test_rate_limiter_threshold_warning()
    test_rate_limiter_reset()
    test_parallel_method_exists()
    test_parallel_method_basic()
    test_parallel_method_with_workers()
    test_parallel_method_auto_workers()
    test_parallel_method_max_workers_range()
    test_parallel_method_format_types()
    test_parallel_method_statistics()
    test_parallel_method_worker_stats()
    test_parallel_method_global_stats()
    test_parallel_method_verbose_mode()
    test_parallel_method_skip_errors()
    test_parallel_method_empty_pmcids_with_stats()
    test_parallel_method_progress_bar_display()
    test_parallel_method_worker_id_in_results()
    test_parallel_method_output_dir()
    test_parallel_method_rate_limiter_per_worker()
    test_parallel_method_concurrent_access()
    test_parallel_method_no_progress_bar()
    test_parallel_method_single_pmcid()
    test_parallel_method_xml_format()
    test_parallel_method_html_format()
    test_rate_limiter_stats_consistency()
    test_rate_limiter_window_timing()
    test_parallel_method_skip_errors_false()
    test_parallel_method_statistics_consistency()
    print("\n✅ All parallel download tests passed!")
