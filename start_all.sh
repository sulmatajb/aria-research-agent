#!/bin/bash
# ARIA — launch all agents in separate Terminal windows

DIR="/Users/besniksulmataj/Desktop/Besnik AI/DBA/research-agents"

osascript <<EOF
tell application "Terminal"
    activate

    -- Supervisor
    do script "cd '$DIR' && echo '🤖 ARIA Supervisor' && python3 agents/supervisor.py"

    -- Perplexity Agent
    do script "cd '$DIR' && echo '🔍 Perplexity Agent' && python3 agents/perplexity_agent.py"

    -- Firecrawl Agent
    do script "cd '$DIR' && echo '🕷  Firecrawl Agent' && python3 agents/firecrawl_agent.py"

    -- Synthesizer Agent
    do script "cd '$DIR' && echo '✍️  Synthesizer Agent' && python3 agents/synthesizer_agent.py"

    -- Telegram Bot
    do script "cd '$DIR' && echo '📱 ARIA Telegram Bot' && python3 telegram_bot.py"

    -- Live Dashboard
    do script "cd '$DIR' && echo '📊 ARIA Dashboard' && sleep 3 && python3 dashboard.py"

end tell
EOF

echo "✅ ARIA system launched in 6 Terminal windows."
