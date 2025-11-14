"""
API client modules for PyEuropePMC.

This module contains all the client classes for interacting with
different Europe PMC APIs including search, articles, full text, and FTP downloads.
"""

from .article import ArticleClient
from .ftp_downloader import FTPDownloader
from .fulltext import FullTextClient, ProgressInfo
from .search import EuropePMCError, SearchClient

__all__ = [
    "ArticleClient",
    "FTPDownloader",
    "FullTextClient",
    "ProgressInfo",
    "EuropePMCError",
    "SearchClient",
]
