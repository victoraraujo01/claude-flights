---
name: flights
description: Search Google Flights for ticket prices and manage a trip watchlist. Use when user mentions flights, trips, travel prices, ticket tracking, or says /flights.
user-invocable: true
allowed-tools: [Bash, Read, Write, Edit]
---

# Google Flights Price Tracker

You manage a trip watchlist and search Google Flights for the cheapest tickets. The trip list is stored in `trips.json` at the project root. The search engine is `search_flights.py`.

## Trip Management

Interpret the user's natural language to manage trips. Supported actions:

### Add a trip
When the user wants to add/track a trip, create or update `trips.json` (an array of trip objects).

**Trip schema:**
```json
{
  "id": 1,
  "type": "round-trip",
  "origin": "JFK",
  "destination": "LHR",
  "date_window_start": "2026-03-15",
  "date_window_end": "2026-03-25",
  "trip_length_min": 5,
  "trip_length_max": 8,
  "passengers": 1,
  "seat_class": "economy",
  "label": "NYC to London spring trip"
}
```

Rules:
- `id`: Auto-increment integer. Read existing trips to find the max ID, then add 1.
- `type`: `"one-way"` or `"round-trip"`. Infer from context; default to `"round-trip"` unless user says otherwise.
- `origin` / `destination`: **IATA 3-letter airport codes**. Resolve city names to the primary airport code (e.g., "NYC" → "JFK", "London" → "LHR", "Paris" → "CDG", "Tokyo" → "NRT", "São Paulo" → "GRU", "LA" → "LAX", "San Francisco" → "SFO", "Chicago" → "ORD"). If a city has multiple major airports and the user doesn't specify, ask which one. Use your knowledge for any airport code.
- `date_window_start` / `date_window_end`: The flexible departure window in `YYYY-MM-DD` format. Parse natural language like "mid March" → Mar 10-20, "March" → Mar 1-31, "next week" → compute from today's date, "March 15-25" → exact.
- `trip_length_min` / `trip_length_max`: For round-trips only. Number of days. Parse "5-8 day trip" → min=5, max=8. Parse "1 week trip" → min=7, max=7. Parse "about a week" → min=5, max=9. For one-way trips, set both to `null`.
- `passengers`: Default 1. Parse "2 adults" → 2.
- `seat_class`: One of `"economy"`, `"premium-economy"`, `"business"`, `"first"`. Default `"economy"`.
- `label`: A short human-readable description. Generate from context.

If `trips.json` doesn't exist, create it with `[]` first, then add the trip.

### List trips
When the user says "list trips", "show trips", "what trips am I tracking", etc., read `trips.json` and display as a formatted table:

| ID | Label | Route | Type | Window | Length | Pax | Class |
|----|-------|-------|------|--------|--------|-----|-------|
| 1 | NYC-London spring | JFK → LHR | RT | Mar 15-25 | 5-8d | 1 | economy |

### Remove a trip
When the user says "remove trip 2", "delete the London trip", etc., remove it from `trips.json` by matching ID or label, and confirm.

### Edit a trip
When the user says "change trip 1 dates to April", "update the London trip to business class", etc., modify the matching trip in `trips.json`.

## Price Search

When the user says "check prices", "search flights", "how much are flights", "run search", etc.:

### Step 1: Estimate request count
Calculate total queries before running:
- **One-way trips**: `(date_window_end - date_window_start).days + 1` requests per trip
- **Round-trip**: `num_departure_dates × (trip_length_max - trip_length_min + 1)` requests per trip

Sum across all trips. Each request takes ~3.5 seconds on average (2-5s random delay).

If total > 100 requests or estimated time > 5 minutes, warn the user and ask for confirmation before proceeding. Suggest narrowing date windows or trip lengths if too large.

### Step 2: Run the search
```bash
python3 search_flights.py
```

The script outputs JSON to stdout and progress to stderr. The search may take several minutes.

### Step 3: Present results
Parse the JSON output and present a clean markdown report. For each trip:

**Trip 1: NYC to London spring trip (JFK → LHR, round-trip)**
| # | Depart | Return | Price | Airline | Duration | Stops |
|---|--------|--------|-------|---------|----------|-------|
| 1 | Mar 18 | Mar 24 | $523 | Norse Atlantic | 7h 20m | 0 |
| 2 | Mar 20 | Mar 26 | $547 | British Airways | 7h 45m | 0 |
| 3 | Mar 17 | Mar 23 | $589 | Delta | 8h 10m | 1 |

Also mention:
- How many combinations were searched vs successful
- Any errors encountered
- The overall price level if available (low/typical/high)

### Highlighting
- Highlight the **cheapest option per trip** prominently
- If a trip has no results at all, note it and suggest adjusting dates or airports

## Ambiguity Handling

- If a city name maps to multiple airports, ask the user which one
- If dates are unclear or missing, ask the user
- If the user doesn't specify one-way vs round-trip, assume round-trip
- If the user doesn't specify trip length for a round-trip, ask them
- If the user doesn't specify passengers or class, use defaults (1 adult, economy)

## Common Airport Codes Reference

| City | Code | City | Code |
|------|------|------|------|
| New York (JFK) | JFK | London Heathrow | LHR |
| New York (Newark) | EWR | London Gatwick | LGW |
| Los Angeles | LAX | Paris CDG | CDG |
| San Francisco | SFO | Tokyo Narita | NRT |
| Chicago O'Hare | ORD | Tokyo Haneda | HND |
| Miami | MIA | São Paulo | GRU |
| Atlanta | ATL | Buenos Aires | EZE |
| Dallas | DFW | Mexico City | MEX |
| Seattle | SEA | Toronto | YYZ |
| Boston | BOS | Sydney | SYD |
| Washington Dulles | IAD | Dubai | DXB |
| Denver | DEN | Singapore | SIN |
| Houston | IAH | Hong Kong | HKG |
| Phoenix | PHX | Bangkok | BKK |
| Las Vegas | LAS | Berlin | BER |
| Orlando | MCO | Rome | FCO |
| Minneapolis | MSP | Madrid | MAD |
| Detroit | DTW | Amsterdam | AMS |
| Philadelphia | PHL | Frankfurt | FRA |
| Lisbon | LIS | Barcelona | BCN |
