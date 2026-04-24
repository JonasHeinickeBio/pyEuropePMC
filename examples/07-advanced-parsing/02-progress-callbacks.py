#!/usr/bin/env python3
"""
Progress Callbacks Demo for PyEuropePMC FullTextClient

This script demonstrates the real-time progress tracking capabilities
for batch downloads and long-running operations.

Features demonstrated:
- Real-time progress tracking with callbacks
- Progress bar visualization
- Time estimation and statistics
- Cache hit tracking
- Different callback styles and update intervals

Author: PyEuropePMC Team
"""

import time
from pathlib import Path

# Third-party imports for enhanced visualization
try:
    from tqdm import tqdm

    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False
    print("Note: Install 'tqdm' for enhanced progress bars: pip install tqdm")

# PyEuropePMC imports
from pyeuropepmc import FullTextClient, ProgressInfo


class ProgressTracker:
    """Enhanced progress tracker with multiple visualization options."""

    def __init__(self, use_tqdm: bool = False, title: str = "Download Progress"):
        self.use_tqdm = use_tqdm and TQDM_AVAILABLE
        self.title = title
        self.pbar = None
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        if self.use_tqdm:
            self.pbar = tqdm(total=100, desc=self.title, unit="%")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.pbar:
            self.pbar.close()

    def update(self, progress: ProgressInfo):
        """Update progress display."""
        if self.use_tqdm and self.pbar:
            self._update_tqdm(progress)
        else:
            self._update_console(progress)

    def _update_tqdm(self, progress: ProgressInfo):
        """Update tqdm progress bar."""
        self.pbar.n = progress.progress_percent
        self.pbar.set_description(f"{self.title} - {progress.status}")

        # Create detailed postfix info
        postfix = {
            "success": progress.successful_downloads,
            "failed": progress.failed_downloads,
            "cache": progress.cache_hits,
        }

        if progress.estimated_remaining_time:
            eta_mins = progress.estimated_remaining_time / 60
            postfix["ETA"] = f"{eta_mins:.1f}m"

        self.pbar.set_postfix(postfix)
        self.pbar.refresh()

    def _update_console(self, progress: ProgressInfo):
        """Update console progress display."""
        elapsed = time.time() - self.start_time if self.start_time else 0

        # Create progress bar
        bar_length = 30
        filled_length = int(bar_length * progress.progress_percent / 100)
        bar = "█" * filled_length + "░" * (bar_length - filled_length)

        # Format status line
        status_line = (
            f"\r{self.title}: [{bar}] "
            f"{progress.progress_percent:.1f}% "
            f"({progress.current_item}/{progress.total_items}) "
            f"| Success: {progress.successful_downloads} "
            f"| Failed: {progress.failed_downloads} "
            f"| Cache: {progress.cache_hits} "
            f"| {elapsed:.1f}s"
        )

        if progress.estimated_remaining_time:
            eta_mins = progress.estimated_remaining_time / 60
            status_line += f" | ETA: {eta_mins:.1f}m"

        print(status_line, end="", flush=True)

        # Show current status on new line occasionally
        if progress.current_item % 3 == 0 or progress.progress_percent >= 100:
            print(f"\n  Status: {progress.status}")


def simple_progress_callback(progress: ProgressInfo):
    """Simple progress callback that prints basic info."""
    print(f"Progress: {progress.progress_percent:.1f}% - {progress.status}")


def detailed_progress_callback(progress: ProgressInfo):
    """Detailed progress callback showing comprehensive statistics."""
    print("\n📊 Progress Update:")
    print(
        f"  ├─ Completion: {progress.progress_percent:.1f}% ({progress.current_item}/{progress.total_items})"
    )
    print(f"  ├─ Current: {progress.current_pmcid or 'N/A'} - {progress.status}")
    print(f"  ├─ Success: {progress.successful_downloads} | Failed: {progress.failed_downloads}")
    print(f"  ├─ Cache hits: {progress.cache_hits}")
    print(f"  ├─ Downloaded: {progress.total_downloaded_bytes / 1024 / 1024:.2f} MB")

    if progress.elapsed_time:
        print(f"  ├─ Elapsed: {progress.elapsed_time:.1f}s")

    if progress.estimated_remaining_time:
        print(f"  └─ ETA: {progress.estimated_remaining_time:.1f}s")
    else:
        print(f"  └─ Rate: {progress.completion_rate:.2f} items/sec")


def demo_basic_progress():
    """Demonstrate basic progress tracking."""
    print("🚀 Demo 1: Basic Progress Tracking")
    print("=" * 50)

    client = FullTextClient(enable_cache=True)

    # Sample PMC IDs for testing
    pmcids = [
        "PMC1911200",  # Known available PDF
        "PMC3312970",  # Another available PDF
        "PMC1234567",  # Likely not available (will fail)
        "PMC7654321",  # Another likely failure
    ]

    output_dir = Path("examples/downloads/progress_demo_basic")

    print(f"Downloading {len(pmcids)} articles to {output_dir}")
    print("Using simple progress callback with 2-second intervals")

    try:
        results = client.download_fulltext_batch(
            pmcids=pmcids,
            format_type="pdf",
            output_dir=output_dir,
            skip_errors=True,
            progress_callback=simple_progress_callback,
            progress_update_interval=2.0,
        )

        print("\n✅ Download completed!")
        print(f"Results: {len([r for r in results.values() if r])} successful downloads")

    except Exception as e:
        print(f"❌ Error during download: {e}")


def demo_detailed_progress():
    """Demonstrate detailed progress tracking."""
    print("\n🔍 Demo 2: Detailed Progress Tracking")
    print("=" * 50)

    client = FullTextClient(enable_cache=True)

    # Larger set for more interesting progress
    pmcids = [
        "PMC1911200",
        "PMC3312970",
        "PMC1234567",
        "PMC7654321",
        "PMC9999999",
        "PMC8888888",
    ]

    output_dir = Path("examples/downloads/progress_demo_detailed")

    print(f"Downloading {len(pmcids)} articles to {output_dir}")
    print("Using detailed progress callback with 1-second intervals")

    try:
        results = client.download_fulltext_batch(
            pmcids=pmcids,
            format_type="pdf",
            output_dir=output_dir,
            skip_errors=True,
            progress_callback=detailed_progress_callback,
            progress_update_interval=1.0,
        )

        print("\n✅ Download completed!")
        print(f"Results: {len([r for r in results.values() if r])} successful downloads")

    except Exception as e:
        print(f"❌ Error during download: {e}")


def demo_enhanced_progress():
    """Demonstrate enhanced progress tracking with visual progress bar."""
    print("\n🎨 Demo 3: Enhanced Progress Tracking")
    print("=" * 50)

    client = FullTextClient(enable_cache=True)

    pmcids = [
        "PMC1911200",
        "PMC3312970",
        "PMC1234567",
        "PMC7654321",
        "PMC9999999",
        "PMC8888888",
        "PMC7777777",
        "PMC6666666",
    ]

    output_dir = Path("examples/downloads/progress_demo_enhanced")

    print(f"Downloading {len(pmcids)} articles to {output_dir}")
    print("Using enhanced progress tracker with visual bars")

    # Use tqdm if available, otherwise fall back to console
    use_tqdm = TQDM_AVAILABLE
    print(f"Using {'tqdm' if use_tqdm else 'console'} progress visualization")

    try:
        with ProgressTracker(use_tqdm=use_tqdm, title="PDF Download") as tracker:
            results = client.download_fulltext_batch(
                pmcids=pmcids,
                format_type="pdf",
                output_dir=output_dir,
                skip_errors=True,
                progress_callback=tracker.update,
                progress_update_interval=0.5,
            )

        print("\n✅ Download completed!")
        print(f"Results: {len([r for r in results.values() if r])} successful downloads")

    except Exception as e:
        print(f"❌ Error during download: {e}")


def demo_xml_progress():
    """Demonstrate progress tracking with XML downloads."""
    print("\n📄 Demo 4: XML Download Progress")
    print("=" * 50)

    client = FullTextClient(enable_cache=True)

    pmcids = [
        "PMC1911200",
        "PMC3312970",
        "PMC1234567",
    ]

    output_dir = Path("examples/downloads/progress_demo_xml")

    print(f"Downloading {len(pmcids)} XML articles to {output_dir}")

    try:
        with ProgressTracker(use_tqdm=False, title="XML Download") as tracker:
            results = client.download_fulltext_batch(
                pmcids=pmcids,
                format_type="xml",
                output_dir=output_dir,
                skip_errors=True,
                progress_callback=tracker.update,
                progress_update_interval=1.0,
            )

        print("\n✅ Download completed!")
        print(f"Results: {len([r for r in results.values() if r])} successful downloads")

    except Exception as e:
        print(f"❌ Error during download: {e}")


def demo_progress_statistics():
    """Demonstrate progress statistics and timing."""
    print("\n📈 Demo 5: Progress Statistics")
    print("=" * 50)

    client = FullTextClient(enable_cache=True)

    # Use some known available PMCs and some that will fail
    pmcids = [
        "PMC1911200",  # Should be available
        "PMC3312970",  # Should be available
        "PMC1234567",  # Will likely fail
        "PMC9999999",  # Will likely fail
        "PMC8888888",  # Will likely fail
    ]

    output_dir = Path("examples/downloads/progress_demo_stats")

    print(f"Downloading {len(pmcids)} articles for statistics demo")

    # Collect statistics
    stats = {"callbacks_called": 0, "max_progress": 0, "final_progress": None}

    def stats_callback(progress: ProgressInfo):
        stats["callbacks_called"] += 1
        stats["max_progress"] = max(stats["max_progress"], progress.progress_percent)
        stats["final_progress"] = progress

        print(
            f"Callback #{stats['callbacks_called']}: "
            f"{progress.progress_percent:.1f}% - {progress.status}"
        )

    try:
        start_time = time.time()

        results = client.download_fulltext_batch(
            pmcids=pmcids,
            format_type="pdf",
            output_dir=output_dir,
            skip_errors=True,
            progress_callback=stats_callback,
            progress_update_interval=0.5,
        )

        total_time = time.time() - start_time

        print("\n📊 Final Statistics:")
        print(f"  ├─ Total time: {total_time:.2f}s")
        print(f"  ├─ Callbacks called: {stats['callbacks_called']}")
        print(f"  ├─ Max progress reached: {stats['max_progress']:.1f}%")

        if stats["final_progress"]:
            final = stats["final_progress"]
            print(f"  ├─ Final successful: {final.successful_downloads}")
            print(f"  ├─ Final failed: {final.failed_downloads}")
            print(f"  ├─ Cache hits: {final.cache_hits}")
            print(f"  ├─ Total downloaded: {final.total_downloaded_bytes / 1024:.1f} KB")
            print(f"  └─ Average rate: {final.completion_rate:.2f} items/sec")

        successful_count = len([r for r in results.values() if r])
        print(f"\n✅ Download completed! {successful_count}/{len(pmcids)} successful")

    except Exception as e:
        print(f"❌ Error during download: {e}")


def main():
    """Run all progress callback demonstrations."""
    print("🎯 PyEuropePMC Progress Callbacks Demo")
    print("=" * 60)
    print()
    print("This demo showcases real-time progress tracking capabilities")
    print("for batch downloads and long-running operations.")
    print()

    try:
        # Run all demos
        demo_basic_progress()
        demo_detailed_progress()
        demo_enhanced_progress()
        demo_xml_progress()
        demo_progress_statistics()

        print("\n🎉 All demos completed successfully!")
        print("Check the 'examples/downloads/' directory for downloaded files.")

    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
        raise


if __name__ == "__main__":
    main()
