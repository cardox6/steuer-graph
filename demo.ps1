# One-command demo start: API in its own window, voice agent in this one.
# Usage:  .\demo.ps1            (browser demo via LiveKit Cloud + Agents Playground)
#         .\demo.ps1 console    (terminal mic loop, no LiveKit Cloud needed)
param([string]$Mode = "dev")

Start-Process powershell -ArgumentList '-NoExit', '-Command', 'uv run uvicorn app.main:app --port 8000'
uv run python voice/agent.py $Mode
