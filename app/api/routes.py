from fastapi import APIRouter, File, UploadFile
from pathlib import Path
import tempfile

from app.services.file_handler import read_routes_csv
from app.routes.process_routes import process_routes
from app.services.pdf_parser import parse_route_pdf  # 👈 NEW

router = APIRouter()


@router.post("/process")
async def process_route_file(file: UploadFile = File(...)):
    """
    Receive a CSV file, process all routes, and return a basic status.
    The detailed outputs (links, HTML maps) are written to the outputs/ folder.
    """

    # 1) Save uploaded CSV to a temp directory
    tmp_dir = Path(tempfile.mkdtemp())
    csv_path = tmp_dir / "upload.csv"

    with open(csv_path, "wb") as f:
        f.write(await file.read())

    # 2) Reuse your existing CSV loader (same behavior as CLI)
    df = read_routes_csv(str(csv_path))

    # 3) Call your existing processing logic (same as CLI)
    result = process_routes(
        df=df,
        route_id=None,
        rtype=None,
        split_mobile=False,
    )

    # 4) Return a simple message + result summary
    return {
        "status": "ok",
        "message": "CSV routes processed successfully.",
        "result": result,
    }


@router.post("/process_pdf")
async def process_route_pdf_endpoint(file: UploadFile = File(...)):
    """
    Receive a PDF route sheet, parse stops, and process routes.
    MVP: we only support structured PDFs where each stop line
    starts with an address (line starting with digits).
    """

    # 1) Save uploaded PDF to a temp directory
    tmp_dir = Path(tempfile.mkdtemp())
    pdf_path = tmp_dir / "upload.pdf"

    with open(pdf_path, "wb") as f:
        f.write(await file.read())

    # 2) Parse PDF into a DataFrame compatible with process_routes
    df = parse_route_pdf(str(pdf_path))
    print("DEBUG PDF ROWS:", len(df))
    print(df[["sequence", "address"]].to_string(index=False))

    # Debug (optional): print columns to verify
    print("DEBUG PDF COLUMNS:", list(df.columns))

    # 3) Reuse the same processing logic as CSV
    result = process_routes(
        df=df,
        route_id=None,
        rtype=None,
        split_mobile=False,
    )

    # 4) Return JSON with the same structure we already use
    return {
        "status": "ok",
        "message": "PDF routes processed successfully.",
        "result": result,
    }

