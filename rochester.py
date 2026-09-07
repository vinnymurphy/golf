#!/usr/bin/env python3

import json
from datetime import date, datetime
from pathlib import Path


def get_user_input(date_played: str):
    """"Args:
        date_played: The date associated with the golf round.

    Returns:
        A dictionary containing the player's round information, or
        ``None`` if no player name is entered.
    """
    user_name = input("Enter name (leave blank to finish): ").strip()
    if not user_name:
        return None

    while True:
        user_score = input("Enter one total score or nine hole scores: ").split()
        try:
            scores = [int(score) for score in user_score]
        except ValueError:
            print("Scores must be whole numbers.")
            continue

        if len(scores) in {1, 9}:
            break

        print("Enter either one total score or exactly nine hole scores.")

    return {
        "completed_holes": 9,
        "course": "Rochester Golf Club",
        "date": date_played,
        "hole_scores": [] if len(scores) == 1 else scores,
        "tee_set_name": "Red" if user_name.lower() in {"mike", "don"} else "White",
        "total_gross_score": sum(scores),
        "username": user_name,
    }


if __name__ == "__main__":
    entered_date = input("Enter date (YYYY-MM-DD, leave blank for today): ").strip()
    played_on = entered_date or date.today().isoformat()

    # Ensures a manually entered date is valid.
    datetime.strptime(played_on, "%Y-%m-%d")

    json_data = []

    while True:
        round_data = get_user_input(played_on)
        if round_data is None:
            break
        json_data.append(round_data)

    output_path = Path("data/imports") / f"{played_on}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    json_data.sort(key=lambda round_data: round_data.get("username", "").casefold())

    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(json_data, output_file, indent=2, sort_keys=True)

    print(f"Saved {len(json_data)} round(s) to {output_path}")
