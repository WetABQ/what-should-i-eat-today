#!/usr/bin/env python3
"""CLI entry point for What Should I Eat Today."""

import argparse
import sys
from datetime import date, datetime, timedelta

from src.analyzer import get_analyzer
from src.scraper import (
    fetch_all_menus_sync,
    fetch_menu_sync,
    get_active_dining_halls,
    get_dining_hall_by_slug,
)


def cmd_today(args):
    """Show today's recommendations."""
    meal_type = args.meal or "lunch"
    menu_date = date.today()

    print(f"🔄 Fetching menus for {menu_date}...")

    menu_day = fetch_all_menus_sync(menu_date, [meal_type])
    analyzer = get_analyzer()
    recommendation = analyzer.analyze_day(menu_day, meal_type)

    print()
    print(analyzer.format_recommendation(recommendation))


def cmd_menu(args):
    """Show menu for a specific dining hall."""
    hall = get_dining_hall_by_slug(args.hall)
    if not hall:
        print(f"❌ Unknown dining hall: {args.hall}")
        print("Available halls:")
        for h in get_active_dining_halls():
            print(f"  - {h.slug}")
        sys.exit(1)

    meal_type = args.meal or "lunch"
    menu_date = date.today()

    print(f"🔄 Fetching {meal_type} menu for {hall.name}...")

    items = fetch_menu_sync(hall.slug, menu_date, meal_type)

    if not items:
        print(f"❌ No {meal_type} menu available for {hall.name}")
        sys.exit(1)

    print()
    print(f"🍽️ {hall.name} - {meal_type.capitalize()}")
    print(f"📅 {menu_date}")
    print()

    analyzer = get_analyzer()
    for item in items:
        if analyzer._is_always_available(item.name):
            continue

        score, _, _ = analyzer.score_item(item)
        if score > 0:
            indicator = "⭐"
        elif score < 0:
            indicator = "👎"
        else:
            indicator = "•"

        line = f"{indicator} {item.name}"
        if item.icons:
            icons_str = ", ".join(item.icons[:3])
            line += f" [{icons_str}]"
        print(line)


def cmd_halls(args):
    """List available dining halls."""
    print("🏫 Available Dining Halls:")
    print()
    for hall in get_active_dining_halls():
        status = "✅ Open" if hall.active else "❌ Closed"
        print(f"  {hall.slug}: {hall.name} ({status})")


def cmd_tomorrow(args):
    """Show tomorrow's recommendations."""
    meal_type = args.meal or "lunch"
    menu_date = date.today() + timedelta(days=1)

    print(f"🔄 Fetching menus for {menu_date}...")

    menu_day = fetch_all_menus_sync(menu_date, [meal_type])
    analyzer = get_analyzer()
    recommendation = analyzer.analyze_day(menu_day, meal_type)

    print()
    print(analyzer.format_recommendation(recommendation))


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="What Should I Eat Today - UW-Madison Dining Hall Analyzer"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # today command
    today_parser = subparsers.add_parser("today", help="Show today's recommendations")
    today_parser.add_argument(
        "-m", "--meal",
        choices=["breakfast", "lunch", "dinner"],
        default="lunch",
        help="Meal type (default: lunch)"
    )
    today_parser.set_defaults(func=cmd_today)

    # tomorrow command
    tomorrow_parser = subparsers.add_parser("tomorrow", help="Show tomorrow's recommendations")
    tomorrow_parser.add_argument(
        "-m", "--meal",
        choices=["breakfast", "lunch", "dinner"],
        default="lunch",
        help="Meal type (default: lunch)"
    )
    tomorrow_parser.set_defaults(func=cmd_tomorrow)

    # menu command
    menu_parser = subparsers.add_parser("menu", help="Show menu for a dining hall")
    menu_parser.add_argument("hall", help="Dining hall slug (e.g., gordon-avenue-market)")
    menu_parser.add_argument(
        "-m", "--meal",
        choices=["breakfast", "lunch", "dinner"],
        default="lunch",
        help="Meal type (default: lunch)"
    )
    menu_parser.set_defaults(func=cmd_menu)

    # halls command
    halls_parser = subparsers.add_parser("halls", help="List available dining halls")
    halls_parser.set_defaults(func=cmd_halls)

    args = parser.parse_args()

    if args.command is None:
        # Default to today command
        args.meal = "lunch"
        cmd_today(args)
    else:
        args.func(args)


if __name__ == "__main__":
    main()
