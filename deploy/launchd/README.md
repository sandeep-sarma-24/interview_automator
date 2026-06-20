# Running 24×7 with launchd (bare venv, no Docker)

Two agents: the **API** (mobile dashboard) and the **worker** (discovery → scoring
loop + daily DB backup). The worker holds a file lock so only one ever runs.

```bash
# 1. Edit the absolute paths in both plists to match your checkout.
# 2. Install:
cp deploy/launchd/com.jobcopilot.api.plist    ~/Library/LaunchAgents/
cp deploy/launchd/com.jobcopilot.worker.plist ~/Library/LaunchAgents/

# 3. Load (starts now + on every login/boot):
launchctl load ~/Library/LaunchAgents/com.jobcopilot.api.plist
launchctl load ~/Library/LaunchAgents/com.jobcopilot.worker.plist

# Status / logs:
launchctl list | grep jobcopilot
tail -f data/worker.log data/api.log

# Stop / reload after a code change:
launchctl unload ~/Library/LaunchAgents/com.jobcopilot.worker.plist
launchctl load   ~/Library/LaunchAgents/com.jobcopilot.worker.plist
```

Notes
- The worker runs a DB backup once per UTC day to `data/backups/`. For true
  durability, sync `data/backups/` (and `data/resumes/`) **off the laptop** with
  a separate tool — a single failed SSD is still a single point of failure.
- Bind the API to your Tailscale interface via `SCRAPER_API_HOST` in `.env`;
  do not expose `0.0.0.0`.
- `caffeinate -s` (or Energy Saver settings) keeps the laptop awake for 24×7 use.
