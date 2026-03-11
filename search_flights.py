#!/usr/bin/env python3
"""Google Flights price search engine for the /flights Claude Code skill.

Reads trips.json, queries Google Flights via fast-flights, and outputs
a structured JSON report to stdout. Progress messages go to stderr.
"""

import json
import random
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

try:
    from fast_flights import FlightQuery, Passengers, create_query, get_flights
except ImportError:
    print("Error: fast-flights is not installed. Run: pip install --pre fast-flights==3.0rc0", file=sys.stderr)
    sys.exit(1)

TRIPS_FILE = Path(__file__).parent / "trips.json"
PRICE_MARGIN = 100  # R$ margin for price tiers
MAX_TIERS = 3  # max price tiers per category


def load_trips() -> list:
    if not TRIPS_FILE.exists():
        print(f"Error: {TRIPS_FILE} not found. Add trips first.", file=sys.stderr)
        sys.exit(1)
    with open(TRIPS_FILE) as f:
        trips = json.load(f)
    if not trips:
        print("Error: trips.json is empty. Add trips first.", file=sys.stderr)
        sys.exit(1)
    return trips


def generate_combinations(trip: dict) -> list:
    """Generate date combinations for a trip based on its window and trip length."""
    start = datetime.strptime(trip["date_window_start"], "%Y-%m-%d")
    end = datetime.strptime(trip["date_window_end"], "%Y-%m-%d")
    combos = []

    if trip["type"] == "one-way":
        d = start
        while d <= end:
            combos.append({"departure": d.strftime("%Y-%m-%d"), "return": None})
            d += timedelta(days=1)
    else:
        length_min = trip.get("trip_length_min") or 1
        length_max = trip.get("trip_length_max") or length_min
        d = start
        while d <= end:
            for length in range(length_min, length_max + 1):
                ret = d + timedelta(days=length)
                combos.append({
                    "departure": d.strftime("%Y-%m-%d"),
                    "return": ret.strftime("%Y-%m-%d"),
                })
            d += timedelta(days=1)

    return combos


def build_tiers(flights: list) -> list:
    """Given a list of flights sorted by price, return up to MAX_TIERS price tiers."""
    if not flights:
        return []
    tiers = []
    remaining = flights[:]
    while remaining and len(tiers) < MAX_TIERS:
        base_price = remaining[0]["price_numeric"]
        tier_max = base_price + PRICE_MARGIN
        in_tier = [f for f in remaining if f["price_numeric"] <= tier_max]
        remaining = [f for f in remaining if f["price_numeric"] > tier_max]
        tiers.append({
            "price_range": f"R${int(base_price)}–R${int(base_price + PRICE_MARGIN)}",
            "options": in_tier,
        })
    return tiers


def fmt_time(t) -> str:
    h = t[0] if len(t) > 0 else 0
    m = t[1] if len(t) > 1 else 0
    return f"{h:02d}:{m:02d}"


def fmt_duration(minutes: int) -> str:
    return f"{minutes // 60}h {minutes % 60}m"


def query_one(trip: dict, combo: dict) -> list:
    """Query flights for a single date combination. Returns list of result dicts."""
    origin = trip["origin"]
    dest = trip["destination"]
    seat = trip.get("seat_class", "economy")
    passengers = Passengers(adults=trip.get("passengers", 1))

    flights_list = [FlightQuery(date=combo["departure"], from_airport=origin, to_airport=dest)]
    trip_type = "one-way"

    if trip["type"] == "round-trip" and combo["return"]:
        flights_list.append(FlightQuery(date=combo["return"], from_airport=dest, to_airport=origin))
        trip_type = "round-trip"

    query = create_query(
        flights=flights_list,
        seat=seat,
        trip=trip_type,
        passengers=passengers,
        currency="BRL",
    )

    result = get_flights(query)

    results = []
    for fl in result:
        total_duration = sum(f.duration for f in fl.flights)
        first_leg = fl.flights[0]
        last_leg = fl.flights[-1]
        stops = len(fl.flights) - 1

        results.append({
            "departure_date": combo["departure"],
            "return_date": combo["return"],
            "price": f"R${fl.price}",
            "price_numeric": float(fl.price),
            "airline": ", ".join(fl.airlines) if fl.airlines else "Unknown",
            "duration": fmt_duration(total_duration),
            "stops": stops,
            "departure_time": fmt_time(first_leg.departure.time),
            "arrival_time": fmt_time(last_leg.arrival.time),
            "arrival_time_ahead": "",
            "is_best": False,
        })

    return results


def search_trip(trip: dict) -> dict:
    """Search all date combinations for a single trip."""
    combos = generate_combinations(trip)
    total = len(combos)
    label = trip.get("label", f"{trip['origin']}->{trip['destination']}")

    print(f"\n--- Trip {trip['id']}: {label} ({total} combinations) ---", file=sys.stderr)

    all_results = []
    successful = 0
    no_results = 0
    failed = 0
    errors = []

    for i, combo in enumerate(combos):
        if i > 0:
            delay = random.uniform(2.0, 5.0)
            time.sleep(delay)

        desc = combo["departure"]
        if combo["return"]:
            desc += f" -> {combo['return']}"

        print(f"  [{i + 1}/{total}] {desc}...", file=sys.stderr, end=" ", flush=True)

        try:
            results = query_one(trip, combo)
            if results:
                all_results.extend(results)
                successful += 1
                print(f"OK ({len(results)} flights)", file=sys.stderr)
            else:
                no_results += 1
                print("no results", file=sys.stderr)

        except Exception as e:
            # Retry once after 10s
            print("error, retrying...", file=sys.stderr, end=" ", flush=True)
            time.sleep(10)
            try:
                results = query_one(trip, combo)
                if results:
                    all_results.extend(results)
                    successful += 1
                    print(f"OK ({len(results)} flights)", file=sys.stderr)
                else:
                    no_results += 1
                    print("no results", file=sys.stderr)
            except Exception as e2:
                failed += 1
                err_msg = f"Trip {trip['id']}: {desc} - {str(e2)[:100]}"
                errors.append(err_msg)
                print(f"FAILED: {e2}", file=sys.stderr)

    # Deduplicate by (airline, departure_time, arrival_time, price, departure_date, return_date)
    seen = set()
    unique = []
    for r in all_results:
        key = (r["airline"], r["departure_time"], r["arrival_time"], r["price"],
               r["departure_date"], r["return_date"])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    # Group by date combination and build tiered results
    combos_map = defaultdict(list)
    for r in unique:
        key = (r["departure_date"], r["return_date"])
        combos_map[key].append(r)

    by_combination = []
    for (dep, ret), flights in sorted(combos_map.items()):
        flights_sorted = sorted(flights, key=lambda x: x["price_numeric"])

        # Direct flights category
        direct_flights = [f for f in flights_sorted if f["stops"] == 0]
        direct_tiers = build_tiers(direct_flights) or None

        # Per-airline category
        airlines_map = defaultdict(list)
        for f in flights_sorted:
            main_airline = f["airline"].split(",")[0].strip()
            airlines_map[main_airline].append(f)
        by_airline = {
            airline: build_tiers(afl)
            for airline, afl in sorted(airlines_map.items())
        }

        by_combination.append({
            "departure_date": dep,
            "return_date": ret,
            "direct": direct_tiers,
            "by_airline": by_airline,
        })

    return {
        "id": trip["id"],
        "label": label,
        "origin": trip["origin"],
        "destination": trip["destination"],
        "type": trip["type"],
        "total_combinations": total,
        "successful_queries": successful,
        "no_results": no_results,
        "failed_queries": failed,
        "by_combination": by_combination,
        "errors": errors,
    }


def main():
    trips = load_trips()
    total_combos = sum(len(generate_combinations(t)) for t in trips)
    est_time = total_combos * 3.5  # average 3.5s per request

    print(f"Searching {len(trips)} trip(s), {total_combos} total combinations", file=sys.stderr)
    print(f"Estimated time: ~{int(est_time)}s ({int(est_time / 60)}m {int(est_time % 60)}s)", file=sys.stderr)

    all_errors = []
    trip_results = []

    for trip in trips:
        result = search_trip(trip)
        all_errors.extend(result.pop("errors", []))
        trip_results.append(result)

    report = {
        "search_time": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "trips": trip_results,
        "errors": all_errors,
    }

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
