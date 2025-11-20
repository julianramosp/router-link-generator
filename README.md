# router-link-generator

A lightweight utility that transforms route data (originally captured from paper sheets or spreadsheets) into GPS-ready navigation links and optional HTML maps.

The purpose of this tool is to digitize analog or manual route instructions and turn them into ready-to-use Google Maps directions, supporting multi-stop routes, optional geocoding, and mobile-friendly segmented navigation.

> ⚠️ This project is **fully generic** and **not associated with any organization, school district, transportation company, or vendor**.  
> It can be used for logistics, deliveries, technicians, transport workflows, field operations, or any process requiring structured navigation.

---

## ✨ Features

- **CSV-based ingestion**  
  Reads and normalizes route data from simple CSV files.

- **Google Maps directions links**  
  - Builds a complete multi-stop URL using raw addresses  
  - Optionally generates a second URL using geocoded coordinates  

- **Mobile-friendly route splitting**  
  Splits long routes into segments to respect waypoint limits on mobile Google Maps.

- **HTML map generation (Folium)**  
  Creates interactive maps with markers and polylines for quick visual validation.

- **Geocoding (Google + OSM)**  
  - Prioritizes Google Maps Geocoding API (if configured)  
  - Fallback to OpenStreetMap Nominatim  
  - Automatic caching to avoid repeated lookups  

- **Clean, modular Python architecture**  
  All logic is divided into services, routes, models, and utilities.

---

## 📂 Project Structure

```bash
route_project/
│
├── app/
│   ├── main.py                  # CLI entry point
│   │
│   ├── config/
│   │   ├── settings.py          # Paths, environment & optional API key
│   │
│   ├── routes/
│   │   ├── process_routes.py    # Orchestration of route processing
│   │   ├── generate_links.py    # URL builders & split logic
│   │   └── utils.py             # Formatting / normalization helpers
│   │
│   ├── services/
│   │   ├── file_handler.py      # CSV loading, cleaning, validation
│   │   ├── geocoding.py         # Geocoding + caching
│   │   ├── cache_store.py       # Local JSON cache handling
│   │   └── mapping.py           # Folium HTML map builder
│   │
│   └── models/
│       └── route_model.py       # Future Pydantic models for API use
│
├── tests/                       # Basic test scaffolding
│
├── data_raw/                    # Input CSV files (gitignored)
├── data_processed/              # Cached data (gitignored)
├── outputs/                     # Generated links & maps (gitignored)
│
├── .gitignore
├── README.md
├── requirements.txt
└── venv/                        # Local virtual environment (gitignored)
⚙️ Installation
1. Clone the repository
bash
 
git clone https://github.com/julianramosp/router-link-generator.git
cd router-link-generator/route_project
2. Create & activate a virtual environment
Windows (PowerShell)
powershell
 
python -m venv venv
venv\Scripts\activate
macOS / Linux
bash
 
python3 -m venv venv
source venv/bin/activate
3. Install dependencies
bash
 
pip install -r requirements.txt
📥 CSV Input Format
The tool expects a CSV with at least:

Column	Required	Description
route_id	✔️	Route identifier (e.g. A1)
school	✔️	Generic grouping field
type	✔️	AM / PM / any category
stop_name	✔️	Human-readable stop
address	✔️	Full address string
notes	Optional	Additional details
time	Optional	Schedule or timestamp
sequence	Optional	Order; will be recalculated

Example:

csv
 
route_id,school,type,stop_name,address,notes,time
A1,Group,AM,Stop 1,"123 Main St, Madison, WI",,
A1,Group,AM,Stop 2,"456 Oak Ave, Madison, WI",,
A1,Group,AM,Stop 3,"789 Elm St, Madison, WI",,
Addresses with commas should be inside quotes.

Place CSV files under data_raw/ (not tracked by git).

🚀 Usage (CLI)
Run the tool with:

bash
 
python -m app.main --csv "..\data_raw\routes_verona.csv" --route A1 --type AM
Optional flags
Flag	Description
--split-mobile	Splits routes into chunks for mobile waypoint limits
--route	Process only a specific route_id
--type	Process only a specific type (AM/PM/etc.)

Examples:

bash
 
python -m app.main --csv "..\data_raw\my_routes.csv"
python -m app.main --csv "..\data_raw\my_routes.csv" --route A1 --type PM
python -m app.main --csv "..\data_raw\my_routes.csv" --split-mobile
📤 Output Files
Files appear in the outputs/ directory:

route_<id>_<type>_link.txt
→ Google Maps link using raw addresses.

route_<id>_<type>_link_coords.txt
→ Google Maps link using geocoded coordinates.

route_<id>_<type>.html
→ Interactive Folium map.

🌐 Geocoding Details
Priority:

Google Maps Geocoding API (if key configured)

OpenStreetMap Nominatim fallback

Local JSON cache in data_processed/geocode_cache.json

This prevents re-geocoding the same address repeatedly.

🧭 Roadmap
FastAPI web interface

Streamlit UI for non-technical users

OCR pipeline to extract routes from photos

Excel support

Docker container

Multi-route batch processing

API authentication layer for deployment

⚖️ Disclaimer
This is a general-purpose routing utility built with anonymized / synthetic data.
It is not affiliated with any transportation company, school system, vendor, or contractor.

📜 License (optional)
If you want, I can generate a standard MIT License file for the repo.

yaml
 

---

# 🚀 SIGUIENTE PASO

Ahora que ya tienes el README:

### Solo ejecuta estos comandos:

```powershell
git add README.md
git commit -m "Replace README with full project documentation"
git push
Y tu repositorio quedará profesional, listo para portafolio y entrevistas.

¿Le damos push? ¿O quieres agregar el MIT license también?






Dijiste:
todo esto va en el readme? por que lo dividiste en partes



ChatGPT dijo:
Sí, Julian: TODO lo que te puse va dentro del README.md como un solo archivo completo.
Lo dividí en secciones solo para que tú lo vieras más claro aquí en el chat, pero es un único bloque continuo, listo para copiar–pegar.

Para evitar confusión, aquí va TODO UNIDO EN UN SOLO BLOQUE, sin divisiones, tal como debe quedar en tu README.md:

📄 README COMPLETO (VERSIÓN FINAL – COPIA TODO ESTO TAL CUAL)
👉 Pídemelo si quieres que te lo entregue también como archivo .md listo para descargar.

markdown
 
# router-link-generator

A lightweight utility that transforms route data (originally captured from paper sheets or spreadsheets) into GPS-ready navigation links and optional HTML maps.

The purpose of this tool is to digitize analog or manual route instructions and turn them into ready-to-use Google Maps directions, supporting multi-stop routes, optional geocoding, and mobile-friendly segmented navigation.

> ⚠️ This project is **fully generic** and **not associated with any organization, school district, transportation company, or vendor**.  
> It can be used for logistics, deliveries, technicians, transport workflows, field operations, or any process requiring structured navigation.

---

## ✨ Features

- **CSV-based ingestion**  
  Reads and normalizes route data from simple CSV files.

- **Google Maps directions links**  
  - Builds a complete multi-stop URL using raw addresses  
  - Optionally generates a second URL using geocoded coordinates  

- **Mobile-friendly route splitting**  
  Splits long routes into segments to respect waypoint limits on mobile Google Maps.

- **HTML map generation (Folium)**  
  Creates interactive maps with markers and polylines for quick visual validation.

- **Geocoding (Google + OSM)**  
  - Prioritizes Google Maps Geocoding API (if configured)  
  - Fallback to OpenStreetMap Nominatim  
  - Automatic caching to avoid repeated lookups  

- **Clean, modular Python architecture**  
  All logic is divided into services, routes, models, and utilities.

---

## 📂 Project Structure

```bash
route_project/
│
├── app/
│   ├── main.py                  # CLI entry point
│   │
│   ├── config/
│   │   ├── settings.py          # Paths, environment & optional API key
│   │
│   ├── routes/
│   │   ├── process_routes.py    # Orchestration of route processing
│   │   ├── generate_links.py    # URL builders & split logic
│   │   └── utils.py             # Formatting / normalization helpers
│   │
│   ├── services/
│   │   ├── file_handler.py      # CSV loading, cleaning, validation
│   │   ├── geocoding.py         # Geocoding + caching
│   │   ├── cache_store.py       # Local JSON cache handling
│   │   └── mapping.py           # Folium HTML map builder
│   │
│   └── models/
│       └── route_model.py       # Future Pydantic models for API use
│
├── tests/                       # Basic test scaffolding
│
├── data_raw/                    # Input CSV files (gitignored)
├── data_processed/              # Cached data (gitignored)
├── outputs/                     # Generated links & maps (gitignored)
│
├── .gitignore
├── README.md
├── requirements.txt
└── venv/                        # Local virtual environment (gitignored)
⚙️ Installation
1. Clone the repository
bash
 
git clone https://github.com/julianramosp/router-link-generator.git
cd router-link-generator/route_project
2. Create & activate a virtual environment
Windows (PowerShell)
powershell
 
python -m venv venv
venv\Scripts\activate
macOS / Linux
bash
 
python3 -m venv venv
source venv/bin/activate
3. Install dependencies
bash
 
pip install -r requirements.txt
📥 CSV Input Format
The tool expects a CSV with at least:

Column	Required	Description
route_id	✔️	Route identifier (e.g. A1)
school	✔️	Generic grouping field
type	✔️	AM / PM / any category
stop_name	✔️	Human-readable stop
address	✔️	Full address string
notes	Optional	Additional details
time	Optional	Schedule or timestamp
sequence	Optional	Order; will be recalculated

Example:

csv
 
route_id,school,type,stop_name,address,notes,time
A1,Group,AM,Stop 1,"123 Main St, Madison, WI",,
A1,Group,AM,Stop 2,"456 Oak Ave, Madison, WI",,
A1,Group,AM,Stop 3,"789 Elm St, Madison, WI",,
Addresses with commas should be inside quotes.

Place CSV files under data_raw/ (not tracked by git).

🚀 Usage (CLI)
Run the tool with:

bash
 
python -m app.main --csv "..\data_raw\routes_verona.csv" --route A1 --type AM
Optional flags
Flag	Description
--split-mobile	Splits routes into chunks for mobile waypoint limits
--route	Process only a specific route_id
--type	Process only a specific type (AM/PM/etc.)

Examples:

bash
 
python -m app.main --csv "..\data_raw\my_routes.csv"
python -m app.main --csv "..\data_raw\my_routes.csv" --route A1 --type PM
python -m app.main --csv "..\data_raw\my_routes.csv" --split-mobile
📤 Output Files
Files appear in the outputs/ directory:

route_<id>_<type>_link.txt
→ Google Maps link using raw addresses.

route_<id>_<type>_link_coords.txt
→ Google Maps link using geocoded coordinates.

route_<id>_<type>.html
→ Interactive Folium map.

🌐 Geocoding Details
Priority:

Google Maps Geocoding API (if key configured)

OpenStreetMap Nominatim fallback

Local JSON cache in data_processed/geocode_cache.json

This prevents re-geocoding the same address repeatedly.

🧭 Roadmap
FastAPI web interface

Streamlit UI for non-technical users

OCR pipeline to extract routes from photos

Excel support

Docker container

Multi-route batch processing

API authentication layer for deployment

⚖️ Disclaimer
This is a general-purpose routing utility built with anonymized / synthetic data.
It is not affiliated with any transportation company, school system, vendor, or contractor.

📜 License (optional)
If you want, I can generate a standard MIT License file for the repo.

yaml
 

---

# 🚀 **¿QUÉ SIGUE AHORA?**

1. Abre tu `README.md`
2. Borra todo lo que tiene
3. Pega **exactamente todo lo de arriba**
4. Guarda

Luego hacemos:

```powershell
git add README.md
git commit -m "Replace README with full documentation"
git push
¿Quieres que prepare el LICENSE MIT también?






Dijiste:
puedes poner toda la info en un solo texto? es que asi es mas dificil e ineficiente para pegarlo



ChatGPT dijo:
Claro, Julian.
Aquí tienes TODO el README completo en un solo bloque, limpio, continuo, sin separaciones y listo para copiar/pegar directamente en tu archivo README.md sin editar nada.

📄 README COMPLETO (VERSIÓN FINAL — COPIA TODO LO QUE ESTÁ ABAJO)
markdown
 
# router-link-generator

A lightweight utility that transforms route data (originally captured from paper sheets or spreadsheets) into GPS-ready navigation links and optional HTML maps. The purpose of this tool is to digitize analog or manual route instructions and turn them into ready-to-use Google Maps directions, supporting multi-stop routes, optional geocoding, and mobile-friendly segmented navigation.

> ⚠️ This project is fully generic and not associated with any organization, school district, transportation company, or vendor. It can be used for logistics, deliveries, technicians, transport workflows, field operations, or any process requiring structured navigation.

## ✨ Features

- CSV-based ingestion: reads and normalizes route data from simple CSV files.  
- Google Maps directions links:
  - Builds a complete multi-stop URL using raw addresses.
  - Optionally generates a second URL using geocoded coordinates.
- Mobile-friendly route splitting: respects waypoint limits on Google Maps mobile.
- HTML map generation (via Folium) for visual route validation.
- Geocoding (Google + OSM) with automatic caching.
- Clean, modular Python architecture divided into services, routes, models, and utilities.

## 📂 Project Structure

route_project/
│
├── app/
│ ├── main.py
│ ├── config/
│ │ └── settings.py
│ ├── routes/
│ │ ├── process_routes.py
│ │ ├── generate_links.py
│ │ └── utils.py
│ ├── services/
│ │ ├── file_handler.py
│ │ ├── geocoding.py
│ │ ├── cache_store.py
│ │ └── mapping.py
│ └── models/
│ └── route_model.py
│
├── tests/
├── data_raw/ (ignored)
├── data_processed/ (ignored)
├── outputs/ (ignored)
├── .gitignore
├── README.md
├── requirements.txt
└── venv/ (ignored)

shell
 

## ⚙️ Installation

### 1. Clone the repository

git clone https://github.com/julianramosp/router-link-generator.git
cd router-link-generator/route_project

ruby
 

### 2. Create & activate a virtual environment

**Windows (PowerShell):**

python -m venv venv
venv\Scripts\activate

makefile


**macOS/Linux:**

python3 -m venv venv
source venv/bin/activate

shell
 

### 3. Install dependencies

pip install -r requirements.txt

diff


## 📥 CSV Input Format

Required columns:  
- route_id  
- school  
- type  
- stop_name  
- address  

Optional:  
- notes  
- time  
- sequence (auto-recalculated if missing)

**Example CSV:**

route_id,school,type,stop_name,address,notes,time
A1,Group,AM,Stop 1,"123 Main St, Madison, WI",,
A1,Group,AM,Stop 2,"456 Oak Ave, Madison, WI",,
A1,Group,AM,Stop 3,"789 Elm St, Madison, WI",,

csharp
 

> Place CSV files inside `data_raw/` — this folder is not tracked by git.

## 🚀 Usage (CLI)

Run the tool with:

python -m app.main --csv "..\data_raw\routes_verona.csv" --route A1 --type AM

lua
 

### Optional flags

- `--split-mobile` → splits routes into chunks  
- `--route` → process a specific route_id  
- `--type` → process a specific type (AM/PM/etc.)

Examples:

python -m app.main --csv "..\data_raw\my_routes.csv"
python -m app.main --csv "..\data_raw\my_routes.csv" --route A1 --type PM
python -m app.main --csv "..\data_raw\my_routes.csv" --split-mobile

markdown
 

## 📤 Output Files

Generated inside `outputs/`:

- `route_<id>_<type>_link.txt` — Google Maps link using raw addresses  
- `route_<id>_<type>_link_coords.txt` — link using geocoded coordinates  
- `route_<id>_<type>.html` — Folium interactive map  

## 🌐 Geocoding Details

Priority order:

1. Google Maps Geocoding API (if a key is configured)  
2. OpenStreetMap Nominatim (fallback)  
3. Local JSON cache (`data_processed/geocode_cache.json`)

This prevents repeated external geocoding.

## 🧭 Roadmap

- FastAPI web interface  
- Streamlit UI  
- OCR pipeline to extract routes from photos  
- Excel/XLSX support  
- Docker image  
- Multi-route batch processing  
- API authentication layer  

## ⚖️ Disclaimer

This tool is for general-purpose routing automation with synthetic or anonymized data. It is not affiliated with any transportation company, school system, or organization.

## 📜 License (optional)

Ask if you want a standard MIT license added.