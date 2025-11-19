"""
File I/O helpers: read CSV and basic normalization for your routes table.
"""
from pathlib import Path
from typing import List
import os
import pandas as pd
import numpy as np
from app.config.settings import DATA_RAW

def read_routes_csv(csv_path: str | None = None) -> pd.DataFrame:
    csv = csv_path or str(DATA_RAW / "routes_verona.csv")
    if not os.path.exists(csv):
        raise FileNotFoundError(f"CSV not found: {csv}")

    df = pd.read_csv(csv, dtype=str, engine="python")
    # Basic cleanup
    for col in ["route_id", "school", "type", "stop_name", "address", "notes", "time"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # Drop junk rows (nan route/type/address)
    df = df.replace({"nan": np.nan, "NaN": np.nan, "NAN": np.nan})
    df = df.dropna(subset=["route_id", "type", "address"])

    # Uppercase type
    if "type" in df.columns:
        df["type"] = df["type"].str.upper()

    # Validate required columns
    required = {"route_id", "school", "type", "stop_name", "address"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns in CSV: {missing}")

    # Ensure notes
    if "notes" not in df.columns:
        df["notes"] = ""

    # Robust resequencing per (route_id, type)
    df["__seq_num"] = pd.to_numeric(df.get("sequence", pd.NA), errors="coerce")
    df["__row"] = range(len(df))
    df = df.sort_values(["route_id", "type", "__seq_num", "__row"], kind="mergesort")
    df["sequence"] = df.groupby(["route_id", "type"]).cumcount() + 1
    df = df.drop(columns=["__seq_num", "__row"])

    return df

def extract_addresses_from_subset(subset: pd.DataFrame) -> List[str]:
    return subset["address"].astype(str).tolist()

