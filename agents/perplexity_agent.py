#!/usr/bin/env python3
"""ARIA Perplexity Agent — runs academic literature searches."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
import requests
import db
import config

db.init()

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"

SYSTEM = """You are a precise academic research assistant.
Given a search query, find peer-reviewed papers and reports.
For each result return a JSON array with objects containing:
  title, authors (array of "Last, First" strings), year, journal, doi, url, abstract (1-2 sentences)
Prioritize: papers from 2018-2026, IEEE/Elsevier/arXiv/MDPI sources, papers with verifiable DOIs.
Do NOT invent paper details. If uncertain about a field, use null."""


def search(query, purpose):
    headers = {
        "Authorization": f"Bearer {config.PERPLEXITY_API_KEY}",
        "Content-Type": "application/json"
    }
    body = {
        "model": "sonar-pro",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Query: {query}\nContext: {purpose}"}
        ],
        "return_citations": True,
        "return_images": False,
        "max_tokens": 2500
    }
    resp = requests.post(PERPLEXITY_URL, headers=headers, json=body, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return {
        "response":   data["choices"][0]["message"]["content"],
        "citations":  data.get("citations", []),
        "query":      query
    }


def main():
    db.log('perplexity', "Perplexity Agent starting")
    print("🔍 Perplexity Agent running. Ctrl+C to stop.\n")
    while True:
        try:
            for task in db.get_pending_tasks('perplexity'):
                if task['type'] != 'search':
                    continue
                payload = json.loads(task['payload'])
                db.update_task(task['id'], status='in_progress')
                db.log('perplexity', f"Searching: {payload['query']}", task_id=task['id'])
                try:
                    result = search(payload['query'], payload.get('purpose', ''))
                    db.update_task(task['id'], status='done', result=result)
                    db.log('perplexity', f"Done #{task['id']}", task_id=task['id'])
                except Exception as e:
                    db.log('perplexity', f"Search failed: {e}", level='error', task_id=task['id'])
                    db.update_task(task['id'], status='failed', result={'error': str(e)})
        except KeyboardInterrupt:
            print("\nPerplexity Agent stopped.")
            break
        except Exception as e:
            db.log('perplexity', f"Loop error: {e}", level='error')
        time.sleep(5)


if __name__ == '__main__':
    main()
