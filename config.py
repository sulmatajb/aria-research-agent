import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

ANTHROPIC_API_KEY  = os.getenv('ANTHROPIC_API_KEY', '')
PERPLEXITY_API_KEY = os.getenv('PERPLEXITY_API_KEY', '')
FIRECRAWL_API_KEY  = os.getenv('FIRECRAWL_API_KEY', '')
TELEGRAM_TOKEN     = os.getenv('TELEGRAM_TOKEN', '')
ZOTERO_LOCAL       = os.getenv('ZOTERO_LOCAL', 'true').lower() == 'true'
ZOTERO_LIBRARY_ID  = os.getenv('ZOTERO_LIBRARY_ID', '')
ZOTERO_API_KEY     = os.getenv('ZOTERO_API_KEY', 'local')
