from fastapi import APIRouter, File, UploadFile
from pathlib import Path
import tempfile

from app.services.file_handler import read_routes_csv
from app.routes.process_routes import process_routes
from app.services.pdf_parser import parse_route_pdf
from app.routes.utils import merge_fragment_stops

# ✅ Import the cleaning function (you must create it if it doesn't exist yet)
from app.routes.utils import clean_stops  # <-- adjust path if needed

router = APIRouter()


@router.post("/process")
async def process_route_file(file: UploadFile = File(...)):
    """
    Receive a CSV file, process all routes, and return a basic status.
    """
    tmp_dir = Path(tempfile.mkdtemp())
    csv_path = tmp_dir / "upload.csv"

    with open(csv_path, "wb") as f:
        f.write(await file.read())

    df = read_routes_csv(str(csv_path))

    result = process_routes(
        df=df,
        route_id=None,
        rtype=None,
        split_mobile=False,
    )

    return {
        "status": "ok",
        "message": "CSV routes processed successfully.",
        "result": result,
    }


@router.post("/process_pdf")
async def process_route_pdf_endpoint(file: UploadFile = File(...)):
    """
    Receive a PDF route sheet, parse stops, clean stops, and build route links.
    """
    tmp_dir = Path(tempfile.mkdtemp())
    pdf_path = tmp_dir / "upload.pdf"

    with open(pdf_path, "wb") as f:
        f.write(await file.read())

    df = parse_route_pdf(str(pdf_path))

    parsed_stops = (
        df[["sequence", "time", "stop_name", "address"]]
        .sort_values("sequence")
        .to_dict(orient="records")
    )
    parsed_stops = merge_fragment_stops(parsed_stops)

    cleaned_stops, dropped_stops = clean_stops(parsed_stops)

    # IMPORTANT: process_routes must support stops=... (we'll fix process_routes.py next)
    result = process_routes(
        stops=cleaned_stops,
        route_id=None,
        rtype=None,
        split_mobile=False,
    )

    return {
        "status": "ok",
        "message": "PDF routes processed successfully.",
        "parsed_stops_count": len(parsed_stops),
        "clean_stops_count": len(cleaned_stops),
        "dropped_stops_count": len(dropped_stops),
        # For debugging; you can remove later:
        "parsed_stops": parsed_stops,
        "dropped_stops": dropped_stops,
        "result": result,
    }