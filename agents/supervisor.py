#!/usr/bin/env python3
"""ARIA Supervisor — orchestrates Perplexity, Firecrawl, Synthesizer agents."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
import requests
import anthropic
import db
import config

db.init()
client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """You are ARIA — Autonomous Research Intelligence Assistant.
You supervise a research team supporting Besnik Sulmataj's DBA dissertation at Westcliff University.

Dissertation: "From Single Home to Grid Edge: Economic Viability and Deployment Architecture for Agentic AI in Residential Energy Management"
Advisor: Christopher Calderon | Graduation: Spring 2027 | Current course: DOC 720 Literature Review

Your team:
- Perplexity Agent (type: search): runs live academic searches, returns paper lists with metadata
- Firecrawl Agent (type: scrape): scrapes a specific URL to verify/extract paper metadata
- Synthesizer Agent (type: synthesize): turns raw findings into APA citations + dissertation-ready summaries

Your job:
1. Receive research tasks from Besnik via Telegram
2. Break them into targeted subtasks for your agents
3. When agents finish, review results — reject poor quality and reassign
4. Add verified papers to Zotero with relevance notes
5. Send Besnik concise summaries of what was found

Dissertation context to guide research:
- Core topic: agentic AI systems for residential HEMS (Home Energy Management Systems)
- Key themes: LLM agents, multi-agent systems, demand response, US electricity markets, FERC Order 2222, VPP economics, TOU tariffs
- Gap in current lit review: several broken/fabricated citations need replacement:
  * Marzbali et al. (2017) — need a real 2017+ paper on MILP for residential scheduling
  * Lissa et al. (2025) — need real LLM-in-building-energy survey paper
  * Figueiredo et al. (2023) — need real MILP-MPC Portuguese household paper
  * Lezama et al. (2023) — need real multi-agent microgrid paper in Ain Shams Eng J
  * Anvari-Moghaddam et al. (2017) — need correct citation details
  * Chen and Lin (2026) — may be fabricated, needs investigation
- Focus on papers 2018-2026, peer-reviewed, US market where possible

Be decisive. Don't ask Besnik clarifying questions. Plan, execute, report."""

TOOLS = [
    {
        "name": "create_search_task",
        "description": "Assign a search query to the Perplexity agent",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "purpose": {"type": "string"}
            },
            "required": ["query", "purpose"]
        }
    },
    {
        "name": "create_scrape_task",
        "description": "Assign a URL to the Firecrawl agent for scraping/verification",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "purpose": {"type": "string"}
            },
            "required": ["url", "purpose"]
        }
    },
    {
        "name": "create_synthesis_task",
        "description": "Ask the Synthesizer to produce APA citations and summaries from raw findings",
        "input_schema": {
            "type": "object",
            "properties": {
                "findings": {"type": "string"},
                "objective": {"type": "string"}
            },
            "required": ["findings", "objective"]
        }
    },
    {
        "name": "add_to_zotero",
        "description": "Add a verified paper to Zotero",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "authors": {"type": "array", "items": {"type": "string"}, "description": "Each author as 'Last, First'"},
                "year": {"type": "string"},
                "journal": {"type": "string"},
                "doi": {"type": "string"},
                "url": {"type": "string"},
                "abstract": {"type": "string"},
                "volume": {"type": "string"},
                "issue": {"type": "string"},
                "pages": {"type": "string"},
                "notes": {"type": "string", "description": "How this paper supports the dissertation"}
            },
            "required": ["title", "authors", "year"]
        }
    },
    {
        "name": "send_to_telegram",
        "description": "Send a message to Besnik via Telegram",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Use markdown. Be concise and useful."}
            },
            "required": ["message"]
        }
    }
]


def zotero_add(paper):
    """Add paper to local Zotero via HTTP API."""
    creators = []
    for author in paper.get('authors', []):
        parts = author.split(',', 1)
        if len(parts) == 2:
            creators.append({"creatorType": "author", "lastName": parts[0].strip(), "firstName": parts[1].strip()})
        else:
            creators.append({"creatorType": "author", "name": author.strip()})

    item = {
        "itemType": "journalArticle",
        "title": paper.get('title', ''),
        "creators": creators,
        "date": paper.get('year', ''),
        "DOI": paper.get('doi', ''),
        "url": paper.get('url', ''),
        "abstractNote": paper.get('abstract', ''),
        "publicationTitle": paper.get('journal', ''),
        "volume": paper.get('volume', ''),
        "issue": paper.get('issue', ''),
        "pages": paper.get('pages', ''),
        "extra": f"ARIA note: {paper.get('notes', '')}"
    }

    try:
        if config.ZOTERO_LOCAL:
            import uuid
            resp = requests.post(
                "http://localhost:23119/connector/saveItems",
                json={"sessionID": str(uuid.uuid4())[:8], "items": [item], "uri": paper.get('url', 'https://zotero.org')},
                headers={"Content-Type": "application/json", "X-Zotero-Connector-API-Version": "3"},
                timeout=10
            )
        else:
            resp = requests.post(
                f"https://api.zotero.org/users/{config.ZOTERO_LIBRARY_ID}/items",
                json=[item],
                headers={"Zotero-API-Key": config.ZOTERO_API_KEY, "Content-Type": "application/json"},
                timeout=10
            )
        if resp.status_code in (200, 201):
            return True, f"Added to Zotero: {paper['title']}"
        return False, f"Zotero error {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        return False, f"Zotero unavailable: {e}"


def execute_tool(name, inp, parent_id, chat_id):
    if name == "create_search_task":
        tid = db.create_task('search', {'query': inp['query'], 'purpose': inp['purpose']},
                             parent_id=parent_id, assigned_to='perplexity')
        db.log('supervisor', f"→ Perplexity task #{tid}: {inp['query']}", task_id=parent_id)
        return f"Search task #{tid} created"

    if name == "create_scrape_task":
        tid = db.create_task('scrape', {'url': inp['url'], 'purpose': inp['purpose']},
                             parent_id=parent_id, assigned_to='firecrawl')
        db.log('supervisor', f"→ Firecrawl task #{tid}: {inp['url']}", task_id=parent_id)
        return f"Scrape task #{tid} created"

    if name == "create_synthesis_task":
        tid = db.create_task('synthesize', {'findings': inp['findings'], 'objective': inp['objective']},
                             parent_id=parent_id, assigned_to='synthesizer')
        db.log('supervisor', f"→ Synthesizer task #{tid}", task_id=parent_id)
        return f"Synthesis task #{tid} created"

    if name == "add_to_zotero":
        ok, msg = zotero_add(inp)
        db.log('supervisor', msg, level='info' if ok else 'error', task_id=parent_id)
        return msg

    if name == "send_to_telegram":
        db.create_task('telegram_response',
                       {'message': inp['message'], 'chat_id': chat_id},
                       assigned_to='telegram')
        return "Queued for Telegram"

    return f"Unknown tool: {name}"


def llm_loop(messages, parent_id, chat_id):
    while True:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages
        )
        messages.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason == "end_turn":
            break

        if resp.stop_reason == "tool_use":
            results = []
            for block in resp.content:
                if block.type == "tool_use":
                    out = execute_tool(block.name, block.input, parent_id, chat_id)
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
            messages.append({"role": "user", "content": results})
        else:
            break


def process_new_requests():
    for task in db.get_pending_tasks('supervisor'):
        if task['type'] != 'user_request':
            continue
        payload = json.loads(task['payload'])
        db.update_task(task['id'], status='in_progress')
        db.log('supervisor', f"New request #{task['id']}: {payload.get('message','')[:80]}", task_id=task['id'])
        try:
            llm_loop(
                [{"role": "user", "content": f"New request from Besnik: {payload.get('message','')}"}],
                task['id'],
                task.get('chat_id')
            )
        except Exception as e:
            db.log('supervisor', f"Error on #{task['id']}: {e}", level='error')
            db.update_task(task['id'], status='failed', result={'error': str(e)})


def review_finished_work():
    for parent in db.get_tasks_needing_review():
        children = db.get_done_children(parent['id'])
        if not children:
            continue

        parent_payload = json.loads(parent['payload'])
        chat_id = parent.get('chat_id')

        parts = []
        for c in children:
            r = c.get('result', '{}')
            if isinstance(r, str):
                try:
                    r = json.loads(r)
                except Exception:
                    r = {'raw': r}
            p = json.loads(c['payload']) if isinstance(c['payload'], str) else c['payload']
            parts.append(f"[{c['type'].upper()} Task #{c['id']}]\nInput: {json.dumps(p)}\nOutput: {json.dumps(r)}")

        findings = "\n\n---\n\n".join(parts)
        original = parent_payload.get('message', 'research task')

        db.log('supervisor', f"Reviewing parent #{parent['id']} — {len(children)} child(ren) done")

        try:
            llm_loop(
                [{"role": "user", "content": (
                    f"Original request: {original}\n\n"
                    f"All subtasks are done. Review results, synthesize if ready, "
                    f"add verified papers to Zotero, and send Besnik a summary.\n\n"
                    f"Results:\n{findings}"
                )}],
                parent['id'],
                chat_id
            )
            # Mark parent done if no new pending children
            pending = (db.get_pending_tasks('perplexity') +
                       db.get_pending_tasks('firecrawl') +
                       db.get_pending_tasks('synthesizer'))
            still_running = [c for c in pending if c.get('parent_id') == parent['id']]
            if not still_running:
                db.update_task(parent['id'], status='done')
        except Exception as e:
            db.log('supervisor', f"Review error on #{parent['id']}: {e}", level='error')


def main():
    db.log('supervisor', "ARIA Supervisor starting")
    print("🤖 ARIA Supervisor running. Ctrl+C to stop.\n")
    while True:
        try:
            process_new_requests()
            review_finished_work()
        except KeyboardInterrupt:
            print("\nSupervisor stopped.")
            break
        except Exception as e:
            db.log('supervisor', f"Loop error: {e}", level='error')
        time.sleep(5)


if __name__ == '__main__':
    main()
