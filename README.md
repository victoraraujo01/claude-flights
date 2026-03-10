# claude-flights

Claude Code skill to search Google Flights for ticket prices and manage a trip watchlist.

## Features

- **Trip watchlist management** — Add, remove, list, and edit trips via natural language
- **Flexible date search** — Specify a departure window and trip length range to explore cheaper options
- **Round-trip and one-way** support
- **Rate-limit aware** — Random 2-5s delays between requests to avoid being blocked
- **Free** — Uses the `fast-flights` library (no paid APIs or browser automation required)
- **Structured reports** — Top 5 cheapest options per trip with price, airline, duration, and stops

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/victoraraujo01/claude-flights.git
cd claude-flights
```

### 2. Install the Python dependency

```bash
pip install -r requirements.txt
```

### 3. Run Claude Code from this directory

```bash
claude
```

The `/flights` skill is automatically discovered from `.claude/skills/flights/SKILL.md`.

## Usage

All interaction happens through the `/flights` slash command inside Claude Code:

```
/flights add a round-trip NYC to London, March 15-25, 5-8 day trip
/flights add one-way SFO to Tokyo April 1-10
/flights list my trips
/flights check prices
/flights remove trip 2
/flights change trip 1 to business class
```

### Adding trips

Trips are specified in natural language. Claude resolves city names to IATA airport codes and infers trip type, date windows, and defaults:

- **Round-trip**: `"NYC to London, March 15-25, 5-8 day trip"` — searches departures within Mar 15-25, with returns 5-8 days after each departure
- **One-way**: `"one-way SFO to Tokyo April 1-10"` — searches each date in the window
- Defaults: 1 adult, economy class, round-trip

### Price search

When you say "check prices", the skill:

1. Estimates total request count and warns if it will take a long time
2. Runs `search_flights.py` which queries Google Flights for every date combination
3. Presents a formatted markdown report with the cheapest options per trip

### Global installation (optional)

To make the skill available across all your projects, copy it to your global Claude config:

```bash
mkdir -p ~/.claude/skills/flights
cp .claude/skills/flights/SKILL.md ~/.claude/skills/flights/
```

Then update the path to `search_flights.py` in `SKILL.md` to use an absolute path.

## How it works

- **`search_flights.py`** — Python script that reads `trips.json`, generates all date combinations within flexible windows, queries Google Flights via `fast-flights` (protobuf-encoded URLs), and outputs structured JSON
- **`.claude/skills/flights/SKILL.md`** — Skill definition that instructs Claude how to manage trips and interpret search results
- **`trips.json`** — Trip watchlist (created automatically on first use, gitignored)

## Requirements

- Python 3.8+
- `fast-flights` (`pip install fast-flights`)
- Claude Code CLI
