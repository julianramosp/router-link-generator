import os
import requests
import json
import re


def strip_html(text: str) -> str:
    return re.sub("<.*?>", "", text)


def main():
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise RuntimeError("Falta la variable de entorno GOOGLE_MAPS_API_KEY")

    # 🔹 Direcciones de prueba (nada real de First Student)
    origin = "Verona, WI"
    destination = "Madison, WI"
    waypoints = [
        "Fitchburg, WI",
    ]

    base_url = "https://maps.googleapis.com/maps/api/directions/json"

    params = {
        "origin": origin,
        "destination": destination,
        "waypoints": "|".join(waypoints),
        "mode": "driving",
        "key": api_key,
    }

    print("Llamando a Directions API...")
    response = requests.get(base_url, params=params)

    print("URL llamada:")
    print(response.url)
    print("HTTP status code:", response.status_code)

    data = response.json()
    print("Status de la API:", data.get("status"))

    if data.get("status") == "OK":
        route = data["routes"][0]
        leg = route["legs"][0]
        print("\nResumen:")
        print("  Origen:  ", leg["start_address"])
        print("  Destino: ", leg["end_address"])
        print("  Distancia:", leg["distance"]["text"])
        print("  Duración: ", leg["duration"]["text"])

        print("\nPrimeros 3 pasos:")
        for step in leg["steps"][:3]:
            instr = strip_html(step["html_instructions"])
            print(" -", instr, f"({step['distance']['text']})")
    else:
        print("\nRespuesta completa para debug:\n")
        print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
