from typing import Literal

import numpy as np
from shapely import Point

"""
All numbers are revised numbers from FY2025

Only those with >50 payroll employees are counted

MOE is also not included

This does not include [statutory boards](https://en.wikipedia.org/wiki/Statutory_boards_of_the_Government_of_Singapore)

This doesn't include PMO either, because those numbers include CPIB, but even after it's removed
still leaving >1k for the Istana does not feel right

And in generally, only those in independent buildings are included

I don't know where to start for those
"""

MHA_UNIFORMED_STAFF = {
    "ICA": 5489,
    "SCDF": 2714,
    "CNB": 775,
    "SPF": 14185,
    "SPS": 1953,
    "HTSS": 288,
}


class GovAgency:

    def __init__(
        self,
        name: str,
        coord: Point,
        name_short: str = None,
        workforce: int = np.nan,
        notes: str = "",
    ):
        self.name = name
        self.geometry = coord
        self.name_short = name_short
        self.workforce = workforce
        self.notes = notes

    @property
    def dict(self):
        return {
            "name": self.name,
            "name_short": self.name_short,
            "geometry": self.geometry,
            "workforce": self.workforce,
            "notes": self.notes,
        }


GOV_AGENCIES = [
    GovAgency(
        name="President's Office", coord=Point(103.843063, 1.306975), workforce=72
    ),
    GovAgency(
        name="Attorney-General's Chambers",
        coord=Point(103.845472, 1.286068),
        workforce=652,
    ),
    # GovAgency(name="Auditor-General's Office", coord=Point(), workforce=195), # in IRAS
    GovAgency(name="Courts", coord=Point(103.842942, 1.286872), workforce=1149),
    GovAgency(name="Parliament", coord=Point(103.850372, 1.289071), workforce=65),
    GovAgency(
        name="Ministry of Social and Family Development",
        name_short="MSF",
        coord=Point(103.839493, 1.333707),
        workforce=3002,
    ),
    GovAgency(
        name="Ministry of Defence",
        name_short="MINDEF",
        coord=Point(103.759303, 1.371481),
        workforce=282,
        notes="2024 number",
    ),
    # GovAgency(
    #     name="Ministry of Sustainability and the Environment",
    #     name_short="MSE",
    #     coord=Point(103.836301, 1.310587),
    #     workforce=240,
    # ),
    GovAgency(
        name="Ministry of Finance",
        name_short="MOF",
        coord=Point(103.849629, 1.290862),
        workforce=2102,
    ),
    GovAgency(
        name="Ministry of Foreign Affairs",
        name_short="MFA",
        coord=Point(103.818371, 1.304551),
        workforce=1611,
    ),
    GovAgency(
        name="Ministry of Health",
        name_short="MOH",
        coord=Point(103.833724, 1.280363),
        workforce=1157,
    ),
    GovAgency(
        name="Ministry of Home Affairs",
        name_short="MHA",
        coord=Point(103.845110, 1.324118),
        workforce=27279 - sum(MHA_UNIFORMED_STAFF.values()),
    ),
    GovAgency(
        name="Ministry of Digital Development and Information",
        name_short="MDDI",
        coord=Point(103.848301, 1.290849),
        workforce=1142,
    ),
    GovAgency(
        name="Ministry of Law",
        name_short="MinLaw",
        coord=Point(103.849629, 1.290862),
        workforce=544,
    ),
    GovAgency(
        name="Ministry of Manpower",
        name_short="MOM",
        coord=Point(103.844267, 1.287451),
        workforce=2325,
    ),
    GovAgency(
        name="Ministry of National Development",
        name_short="MND",
        coord=Point(103.845823, 1.278822),
        workforce=403,
    ),
    # GovAgency(
    #     name="Prime Minister's Office",
    #     name_short="PMO",
    #     coord=Point(),
    #     workforce=1312,
    # ),
    GovAgency(
        name="Ministry of Trade and Industry",
        name_short="MTI",
        coord=Point(103.849629, 1.290862),
        workforce=1113,
    ),
    # GovAgency(
    #     name="Ministry of Transport",
    #     name_short="MOT",
    #     coord=Point(),
    #     workforce=170,
    # ),
    GovAgency(
        name="Ministry of Culture, Community and Youth",
        name_short="MCCY",
        coord=Point(103.845823, 1.278822),
        workforce=797,
    ),
]
