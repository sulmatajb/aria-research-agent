#!/usr/bin/env python3
"""ARIA Synthesizer Agent — turns research findings into dissertation-ready text."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import json
import anthropic
import db
import config

db.init()
client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

SYSTEM = """You are a doctoral research synthesizer for Besnik Sulmataj's DBA dissertation:
"From Single Home to Grid Edge: Economic Viability and Deployment Architecture for Agentic AI in Residential Energy Management"
Westcliff University | Advisor: Christopher Calderon

Given raw research findings, produce structured output with:

1. APA_CITATION: Fully formatted APA 7th edition reference (ready to paste into the reference list)
2. SUMMARY: 2-3 sentence academic summary, focused on relevance to agentic AI for HEMS
3. KEY_CLAIMS: 2-4 bullet points of citable facts from this paper
4. DISSERTATION_USE: One sentence on where/how to cite this in the dissertation
5. RELEVANCE_SCORE: 1-10 (10 = directly relevant to agentic AI HEMS research)
6. CONFIDENCE: high / medium / low — how confident you are the metadata is accurate

If any field is uncertain, say "VERIFY NEEDED" — never fabricate paper details."""


def synthesize(findings, objective):
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        system=SYSTEM,
        messages=[{
            "role": "user",
            "content": f"Objective: {objective}\n\nFindings:\n{findings}"
        }]
    )
    return {
        "synthesis":  resp.content[0].text,
        "objective":  objective
    }


def main():
    db.log('synthesizer', "Synthesizer Agent starting")
    print("✍️  Synthesizer Agent running. Ctrl+C to stop.\n")
    while True:
        try:
            for task in db.get_pending_tasks('synthesizer'):
                if task['type'] != 'synthesize':
                    continue
                payload = json.loads(task['payload'])
                db.update_task(task['id'], status='in_progress')
                db.log('synthesizer', f"Synthesizing task #{task['id']}", task_id=task['id'])
                try:
                    result = synthesize(payload['findings'], payload.get('objective', 'Summarize and cite'))
                    db.update_task(task['id'], status='done', result=result)
                    db.log('synthesizer', f"Done #{task['id']}", task_id=task['id'])
                except Exception as e:
                    db.log('synthesizer', f"Synthesis failed: {e}", level='error', task_id=task['id'])
                    db.update_task(task['id'], status='failed', result={'error': str(e)})
        except KeyboardInterrupt:
            print("\nSynthesizer Agent stopped.")
            break
        except Exception as e:
            db.log('synthesizer', f"Loop error: {e}", level='error')
        time.sleep(5)


if __name__ == '__main__':
    main()
