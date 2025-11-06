"""
Module principal contenant tous les composants de Monitor Agent
"""

# Firecrawl Scraper
from .firecrawl_scraper import (
    FirecrawlScraper,
    ScrapedContent,
    scrape_url
)

# AI Agent
from .ai_agent import (
    AIAgent,
    ParsedInstruction,
    parse_instruction
)

# Content Comparator
from .content_comparator import (
    ContentComparator,
    ComparisonResult,
    compare_content
)

# Sheets Manager
from .sheets_manager import (
    SheetsManager,
    ScrapingLog,
    ComparisonLog,
    create_sheets_manager,
    log_scraping_result,
    log_comparison_result
)

# Gmail Notifier
from .gmail_notifier import (
    GmailNotifier,
    ChangeNotification,
    send_change_notification
)

__all__ = [
    # Scraper
    'FirecrawlScraper',
    'ScrapedContent',
    'scrape_url',
    
    # AI Agent
    'AIAgent',
    'ParsedInstruction',
    'parse_instruction',
    
    # Comparator
    'ContentComparator',
    'ComparisonResult',
    'compare_content',
    
    # Sheets Manager
    'SheetsManager',
    'ScrapingLog',
    'ComparisonLog',
    'create_sheets_manager',
    'log_scraping_result',
    'log_comparison_result',
    
    # Gmail Notifier
    'GmailNotifier',
    'ChangeNotification',
    'send_change_notification',
]
