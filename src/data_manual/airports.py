from typing import Literal

import numpy as np
from shapely import Point


class AirportTerminal:

    def __init__(self, annual_capacity: int, coord: Point, name: str = None):
        self.annual_capacity = annual_capacity
        self.coord = coord
        self.name = name


class Airport:

    def __init__(
        self,
        name: str,
        iata: str,
        icao: int,
        annual_passengers: int,
        osm_id: int,
        terminals: list[AirportTerminal],
    ):
        self.name = name
        self.iata = iata
        self.icao = icao
        self.annual_passengers = annual_passengers
        self.osm_id = osm_id
        self.terminals = terminals

        self.total_capacity = sum([t.annual_capacity for t in self.terminals])

    @property
    def dict(self):
        return {
            "name": self.name,
            "iata": self.iata,
            "icao": self.icao,
            "annual_passengers": self.annual_passengers,
            "osm_id": self.osm_id,
            "terminals": self.terminals,
        }

    def get_terminals_with_pax(self):
        """Return terminal details with capacity-weighted annual passenger counts.

        Distribute the airport's annual passengers in proportion to each
        terminal's share of the total annual handling capacity.

        Returns:
            list[dict]: One dictionary per terminal, in terminal order, with
                ``name`` (airport IATA code followed by the terminal name),
                ``coord`` (the terminal's Shapely Point), and
                ``annual_passengers`` (the allocated passenger count as a float).

        Raises:
            ZeroDivisionError: If terminals exist but total capacity is zero.
        """

        return [
            {
                "name": f"{self.iata} {t.name}",
                "coord": t.coord,
                "annual_passengers": self.annual_passengers
                * t.annual_capacity
                / self.total_capacity,
            }
            for t in self.terminals
        ]


AIRPORTS = [
    Airport(
        name="Changi Airport",
        iata="SIN",
        icao="WSSS",
        annual_passengers=23000000,  # 63000 daily
        osm_id=174037464,
        terminals=[
            AirportTerminal(24000000, Point(103.990510, 1.362032), "T1"),
            AirportTerminal(28000000, Point(103.989018, 1.355387), "T2"),
            AirportTerminal(22000000, Point(103.986652, 1.356250), "T3"),
            AirportTerminal(16000000, Point(103.983412, 1.338134), "T4"),
        ],
    ),
    Airport(
        name="Seletar Airport",
        iata="XSP",
        icao="WSSL",
        annual_passengers=400 * 365,
        osm_id=381760619,
        terminals=[AirportTerminal(700000, Point(103.871500, 1.414550))],
    ),
]
