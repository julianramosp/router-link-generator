from fastapi import APIRouter, File, UploadFile
from pathlib import Path
import tempfile

from app.services.file_handler import read_routes_csv
from app.routes.process_routes import process_route

router = APIRouter()


@router.post("/process")
async def process_route_file(file: UploadFile = File(...)):
    """
    Receive a CSV file, process all routes (grouped by route_id and type),
    and return the processed route segments with Google Maps URLs.
    """

    # 1) Save uploaded CSV to a temporary folder
    tmp_dir = Path(tempfile.mkdtemp())
    csv_path = tmp_dir / "uploaded.csv"

    with open(csv_path, "wb") as f:
        f.write(await file.read())

    try:
        # 2) Read the CSV into a DataFrame
        df = read_routes_csv(str(csv_path))

        # DEBUG: show columns in console to verify names
        print("DEBUG COLUMNS:", list(df.columns))

        # 3) Ensure required columns are present
        required_columns = {"route_id", "type", "address", "sequence"}
        missing = required_columns - set(df.columns)
        if missing:
            return {
                "status": "error",
                "message": f"Missing required columns in CSV: {', '.join(missing)}",
            }

        results = []

        # 4) Group by route_id and type (AM/PM)
        grouped = df.groupby(["route_id", "type"])

        for (route_id, route_type), group in grouped:
            # Sort stops by sequence (correct order of route)
            group_sorted = group.sort_values("sequence")

            # Build the ordered list of stop addresses
            stops = group_sorted["address"].tolist()

            # Skip routes with fewer than 2 stops
            if len(stops) < 2:
                continue

            # 5) Process route using Google Directions API
            route_result = process_route(
                stops=stops,
                route_id=str(route_id),
                route_type=str(route_type),
            )

            results.append(route_result)

        return {
            "status": "ok",
            "total_routes": len(results),
            "routes": results,
        }

    except Exception as e:
        # Print full traceback in console
        import traceback
        traceback.print_exc()

        # Return the error message so we see it in Swagger
        return {
            "status": "error",
            "message": f"Unexpected error: {str(e)}",
        }
