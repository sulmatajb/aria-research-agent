#!/usr/bin/env python3
"""ARIA Firecrawl Agent — scrapes and verifies paper URLs."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
import requests
import db
import config

db.init()

FIRECRAWL_URL = "https://api.firecrawl.dev/v1/scrape"


def scrape(url, purpose):
    headers = {
        "Authorization": f"Bearer {config.FIRECRAWL_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "url": url,
        "formats": ["json"],
        "jsonOptions": {
            "prompt": (
                f"Extract academic paper metadata. Purpose: {purpose}. "
                "Return: title, authors (full names), year, journal, doi, "
                "volume, issue, pages, abstract. If any field is missing say null."
            )
        },
        "onlyMainContent": True
    }
    resp = requests.post(FIRECRAWL_URL, headers=headers, json=body, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    extracted = data.get('data', {}).get('json', {})
    metadata  = data.get('data', {}).get('metadata', {})
    return {
        "url":        url,
        "extracted":  extracted,
        "page_title": metadata.get('title', ''),
        "status":     metadata.get('statusCode', 200)
    }


def main():
    db.log('firecrawl', "Firecrawl Agent starting")
    print("🕷️  Firecrawl Agent running. Ctrl+C to stop.\n")
    while True:
        try:
            for task in db.get_pending_tasks('firecrawl'):
                if task['type'] != 'scrape':
                    continue
                payload = json.loads(task['payload'])
                db.update_task(task['id'], status='in_progress')
                db.log('firecrawl', f"Scraping: {payload['url']}", task_id=task['id'])
                try:
                    result = scrape(payload['url'], payload.get('purpose', 'Extract paper metadata'))
                    db.update_task(task['id'], status='done', result=result)
                    db.log('firecrawl', f"Done #{task['id']}", task_id=task['id'])
                except Exception as e:
                    db.log('firecrawl', f"Scrape failed: {e}", level='error', task_id=task['id'])
                    db.update_task(task['id'], status='failed', result={'error': str(e)})
        except KeyboardInterrupt:
            print("\nFirecrawl Agent stopped.")
            break
        except Exception as e:
            db.log('firecrawl', f"Loop error: {e}", level='error')
        time.sleep(5)


if __name__ == '__main__':
    main()
