"""
CLI entry point for the route project.
Run with:
    python -m app.main --csv "..\\data_raw\\routes_verona.csv" --route A1 --type AM
"""
import argparse
from app.services.file_handler import read_routes_csv
from app.routes.process_routes import process_routes


def main():
    parser = argparse.ArgumentParser(description="Generate route links and maps from CSV.")
    parser.add_argument("--csv", help="Path to input CSV (defaults to data_raw/routes_verona.csv)")
    parser.add_argument("--route", help="Route ID to process (default: all)")
    parser.add_argument("--type", help="Route type AM/PM (use with --route)")
    parser.add_argument(
        "--split-mobile",
        action="store_true",
        help="Split route into mobile-friendly links (<=10 waypoints each)",
    )
    args = parser.parse_args()

    print("[BOOT] route_project starting")
    print(f"[ARGS] csv={args.csv} route={args.route} type={args.type} split_mobile={args.split_mobile}")

    df = read_routes_csv(args.csv)
    print(f"[CSV] loaded rows={len(df)} cols={list(df.columns)}")
    print("[CSV] route/type combos:\n", df[["route_id", "type"]].drop_duplicates().to_string(index=False))

    process_routes(df, args.route, args.type, split_mobile=args.split_mobile)

    print("\nDone ✅")


if __name__ == "__main__":
    main()
