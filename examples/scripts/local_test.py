#!/usr/bin/env python3
"""
Local Testing Script for pyEuropePMC

This script allows you to run tests locally with similar options to the GitHub Actions workflow,
helping you validate changes before pushing to CI/CD.

Usage examples:
    python scripts/local_test.py --help
    python scripts/local_test.py --syntax-only
    python scripts/local_test.py --core-only --modules utils,base,search
    python scripts/local_test.py --full --skip-windows-tests
    python scripts/local_test.py --dry-run --modules fulltext
"""

import argparse
from pathlib import Path
import platform
import subprocess
import sys


class LocalTester:
    """Local testing utility for pyEuropePMC."""

    def __init__(self) -> None:
        self.project_root = Path(__file__).parent.parent
        self.is_windows = platform.system() == "Windows"
        self.python_cmd = "python" if self.is_windows else "python3"

    def run_command(self, cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
        """Run a command with proper error handling."""
        print(f"🔨 Running: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                check=check,
                capture_output=False,  # Show output in real-time
                text=True,
            )
            return result
        except subprocess.CalledProcessError as e:
            print(f"❌ Command failed with exit code {e.returncode}")
            if not check:
                # Return a CompletedProcess object for consistency
                return subprocess.CompletedProcess[str](e.cmd, e.returncode, e.stdout, e.stderr)
            raise

    def check_poetry(self) -> bool:
        """Check if Poetry is available."""
        try:
            result = subprocess.run(
                ["poetry", "--version"], capture_output=True, text=True, check=True
            )
            print(f"✅ Poetry found: {result.stdout.strip()}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ Poetry not found. Please install Poetry first:")
            print("   curl -sSL https://install.python-poetry.org | python3 -")
            return False

    def install_dependencies(self) -> bool:
        """Install project dependencies using Poetry."""
        print("📦 Installing dependencies...")
        try:
            self.run_command(["poetry", "install", "--no-interaction"])
            return True
        except subprocess.CalledProcessError:
            print("❌ Failed to install dependencies")
            return False

    def run_syntax_check(self) -> bool:
        """Run syntax and import checks."""
        print("\n🔍 Running syntax and import checks...")

        # Python files to check
        python_files = [
            "src/pyeuropepmc/__init__.py",
            "src/pyeuropepmc/base.py",
            "src/pyeuropepmc/search.py",
            "src/pyeuropepmc/parser.py",
            "src/pyeuropepmc/fulltext.py",
            "src/pyeuropepmc/ftp_downloader.py",
            "src/pyeuropepmc/error_codes.py",
            "src/pyeuropepmc/exceptions.py",
            "src/pyeuropepmc/utils/helpers.py",
        ]

        # Test syntax compilation
        for file_path in python_files:
            try:
                self.run_command(["poetry", "run", "python", "-m", "py_compile", file_path])
                print(f"✅ Syntax OK: {file_path}")
            except subprocess.CalledProcessError:
                print(f"❌ Syntax Error: {file_path}")
                return False

        # Test imports
        import_tests = [
            (
                "import sys; sys.path.insert(0, 'src'); import pyeuropepmc; "
                "print('SUCCESS: pyeuropepmc imported')"
            ),
            (
                "import sys; sys.path.insert(0, 'src'); "
                "from pyeuropepmc.search import SearchClient; "
                "print('SUCCESS: SearchClient imported')"
            ),
            (
                "import sys; sys.path.insert(0, 'src'); "
                "from pyeuropepmc.fulltext import FullTextClient; "
                "print('SUCCESS: FullTextClient imported')"
            ),
            (
                "import sys; sys.path.insert(0, 'src'); "
                "from pyeuropepmc.ftp_downloader import FTPDownloader; "
                "print('SUCCESS: FTPDownloader imported')"
            ),
        ]

        for test in import_tests:
            try:
                self.run_command(["poetry", "run", "python", "-c", test])
            except subprocess.CalledProcessError:
                print(f"❌ Import test failed: {test[:50]}...")
                return False

        print("✅ All syntax and import checks passed!")
        return True

    def run_module_tests(self, modules: list[str], skip_windows_tests: bool = False) -> bool:
        """Run tests for specific modules."""
        print(f"\n🧪 Running tests for modules: {', '.join(modules)}")

        module_paths = {
            "utils": "tests/utils/",
            "base": "tests/base/",
            "exceptions": "tests/exceptions/",
            "parser": "tests/parser/unit/",
            "search": "tests/search/unit/",
            "fulltext": "tests/fulltext/unit/",
            "ftp": "tests/ftp_downloader/",
        }

        pytest_opts = ["-v", "--tb=short", "--maxfail=5"]

        if self.is_windows and skip_windows_tests:
            pytest_opts.extend(["-m", "not windows_skip"])

        success = True
        for module in modules:
            if module not in module_paths:
                print(f"❌ Unknown module: {module}")
                success = False
                continue

            print(f"\n🔬 Testing {module} module...")
            test_path = module_paths[module]

            cmd = ["poetry", "run", "pytest", test_path] + pytest_opts

            # Special handling for fulltext on Windows
            if module == "fulltext" and self.is_windows and skip_windows_tests:
                print("🪟 Running fulltext tests with Windows compatibility mode...")
                cmd.extend(
                    [
                        "-k",
                        (
                            "not (test_download_pdf_by_pmcid_all_fail or "
                            "test_try_bulk_xml_download_success)"
                        ),
                    ]
                )

            try:
                self.run_command(cmd)
                print(f"✅ {module} tests passed!")
            except subprocess.CalledProcessError:
                print(f"❌ {module} tests failed!")
                success = False

        return success

    def run_linting(self) -> bool:
        """Run code linting and type checking."""
        print("\n🧹 Running code linting...")

        # Ruff linting
        try:
            self.run_command(["poetry", "run", "ruff", "check", ".", "--output-format=github"])
            print("✅ Ruff linting passed!")
        except subprocess.CalledProcessError:
            print("❌ Ruff linting failed!")
            return False

        # MyPy type checking
        try:
            self.run_command(["poetry", "run", "mypy", "src/", "--show-error-codes"])
            print("✅ MyPy type checking passed!")
        except subprocess.CalledProcessError:
            print("❌ MyPy type checking failed!")
            return False

        # Bandit security check
        try:
            result = self.run_command(
                ["poetry", "run", "bandit", "-r", "src/", "-f", "json"], check=False
            )
            if result.returncode == 0:
                print("✅ Security checks passed!")
            else:
                print("⚠️ Security checks found issues (check output above)")
                # Don't fail on security warnings for now
        except subprocess.CalledProcessError:
            print("❌ Security checks failed!")
            return False

        return True

    def run_coverage(self) -> bool:
        """Run tests with coverage analysis."""
        print("\n📊 Running coverage analysis...")

        try:
            # Run tests with coverage
            self.run_command(
                ["poetry", "run", "coverage", "run", "--source=src", "-m", "pytest", "--tb=short"]
            )

            # Generate coverage report
            self.run_command(["poetry", "run", "coverage", "report", "--show-missing"])

            print("✅ Coverage analysis completed!")
            return True
        except subprocess.CalledProcessError:
            print("❌ Coverage analysis failed!")
            return False

    def dry_run(self, modules: list[str], test_level: str, skip_windows_tests: bool) -> None:
        """Show what tests would be run without actually running them."""
        print("\n🏃‍♂️ DRY RUN MODE")
        print("=" * 50)

        print(f"Platform: {platform.system()} ({platform.machine()})")
        print(f"Python: {sys.version}")
        print(f"Working Directory: {self.project_root}")
        print(f"Test Level: {test_level}")
        print(f"Modules: {', '.join(modules)}")
        print(f"Skip Windows Tests: {skip_windows_tests}")

        print("\n📋 Tests that would be executed:")

        if test_level in ["all", "syntax"]:
            print("✅ Syntax and import checks")

        if test_level in ["all", "core"]:
            print("✅ Core module tests:")
            for module in modules:
                status = (
                    "✅"
                    if module in ["utils", "base", "exceptions", "parser", "search", "ftp"]
                    else "❓"
                )
                note = ""
                if module == "fulltext" and self.is_windows and skip_windows_tests:
                    note = " (with Windows compatibility mode)"
                print(f"   {status} {module}{note}")

        if test_level in ["all", "full"]:
            print("✅ Linting and type checking (ruff, mypy, bandit)")
            print("✅ Coverage analysis")

        if test_level == "all":
            print("✅ Integration tests (if available)")

        print("\n⏱️ Estimated runtime:")
        if test_level == "syntax":
            print("   ~2-3 minutes")
        elif test_level == "core":
            print("   ~5-10 minutes")
        elif test_level == "full":
            print("   ~10-15 minutes")
        else:  # all
            print("   ~15-20 minutes")

        print("\n💡 To actually run these tests, remove the --dry-run flag")


def create_argument_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description="Local testing script for pyEuropePMC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --syntax-only                     # Only syntax/import checks
  %(prog)s --core-only --modules utils,base  # Core tests for specific modules
  %(prog)s --full --skip-windows-tests       # Full test suite, skip Windows problematic tests
  %(prog)s --dry-run --modules fulltext      # Show what would run for fulltext module
  %(prog)s --all                             # Complete test suite
        """,
    )

    # Test level options (mutually exclusive)
    level_group = parser.add_mutually_exclusive_group()
    level_group.add_argument(
        "--syntax-only", action="store_true", help="Run only syntax and import checks"
    )
    level_group.add_argument("--core-only", action="store_true", help="Run only core module tests")
    level_group.add_argument(
        "--full", action="store_true", help="Run full test suite (core + linting + coverage)"
    )
    level_group.add_argument("--all", action="store_true", help="Run complete test suite")

    # Module selection
    parser.add_argument(
        "--modules",
        default="all",
        help=(
            "Comma-separated list of modules to test "
            "(utils,base,exceptions,parser,search,fulltext,ftp) or 'all'"
        ),
    )

    # Options
    parser.add_argument(
        "--skip-windows-tests", action="store_true", help="Skip Windows-problematic tests"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be run without executing"
    )
    parser.add_argument("--no-install", action="store_true", help="Skip dependency installation")

    return parser


def determine_test_level(args: argparse.Namespace) -> str:
    """Determine the test level based on arguments."""
    if args.syntax_only:
        return "syntax"
    elif args.core_only:
        return "core"
    elif args.full:
        return "full"
    elif args.all:
        return "all"
    else:
        return "core"  # default


def parse_modules(modules_arg: str) -> list[str]:
    """Parse the modules argument into a list."""
    if modules_arg.lower() == "all":
        return ["utils", "base", "exceptions", "parser", "search", "fulltext", "ftp"]
    else:
        return [m.strip() for m in modules_arg.split(",")]


def run_tests(
    tester: LocalTester, test_level: str, modules: list[str], skip_windows_tests: bool
) -> bool:
    """Run the appropriate tests based on the test level."""
    success = True

    # Run tests based on level
    if test_level in ["syntax", "core", "full", "all"] and not tester.run_syntax_check():
        success = False

    if test_level in ["core", "full", "all"] and not tester.run_module_tests(
        modules, skip_windows_tests
    ):
        success = False

    if test_level in ["full", "all"]:
        if not tester.run_linting():
            success = False

        if not tester.run_coverage():
            success = False

    return success


def main() -> None:
    """Main entry point for the local testing script."""
    parser = create_argument_parser()
    args = parser.parse_args()

    # Determine test level
    test_level = determine_test_level(args)

    # Parse modules
    modules = parse_modules(args.modules)

    tester = LocalTester()

    # Dry run mode
    if args.dry_run:
        tester.dry_run(modules, test_level, args.skip_windows_tests)
        return

    print("🚀 Starting local test execution...")
    print(f"📍 Project root: {tester.project_root}")

    # Check Poetry
    if not tester.check_poetry():
        sys.exit(1)

    # Install dependencies
    if not args.no_install and not tester.install_dependencies():
        sys.exit(1)

    # Run tests
    success = run_tests(tester, test_level, modules, args.skip_windows_tests)

    # Final status
    if success:
        print("\n🎉 All tests completed successfully!")
        print("💡 Your changes look good for CI/CD deployment!")
    else:
        print("\n💥 Some tests failed!")
        print("🔧 Please fix the issues before pushing to CI/CD")
        sys.exit(1)


if __name__ == "__main__":
    main()
