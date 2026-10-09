from typing import Any

import requests


class NasaPowerClient:
    """Cliente aislado para NASA POWER; facilita mocks y reintentos futuros."""

    base_url = "https://power.larc.nasa.gov/api/temporal/daily/point"

    def daily_agronomic_data(self, latitude: float, longitude: float, start: str, end: str) -> dict[str, Any]:
        response = requests.get(
            self.base_url,
            params={
                "parameters": "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,ALLSKY_SFC_SW_DWN,RH2M,EVPTRNS,WS2M,T2MDEW",
                "community": "AG", "longitude": longitude, "latitude": latitude,
                "start": start, "end": end, "format": "JSON",
            },
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
