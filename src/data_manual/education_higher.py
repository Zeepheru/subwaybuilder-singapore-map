"""
Higher education, includes:

- Universities: the 6 autonomous universities + UAS
    - Smaller postgrad campuses are not currently included
- Technical Colleges: the 5 polytechnics and 3 ITEs

Original research is on the Notion page

All demand points are to have id: UNI_<campus.name_short>
"""

from typing import Literal

import numpy as np
from shapely import Point


class Campus:
    """
    Refers to individual campuses (or portions of campuses, for particularly large university campuses)

    Campuses are grouped by institution for later housing distribution.
    """

    def __init__(
        self,
        name: str,
        name_short: str,
        students: int,
        coord: Point,
        institution: str = None,
        notes: str = None,
    ):
        self.name = name
        self.name_short = name_short
        self.coord = coord
        self.students = students
        self.institution = institution
        self.notes = notes

    @property
    def dict(self):
        return {
            "name": self.name,
            "name_short": self.name_short,
            "coord": self.coord,
            "students": self.students,
            "institution": self.institution,
            "notes": self.notes,
        }


# because I have to split the ntu faculties:
_ntu_facs = {
    "Med": (880 + 70 + 163 + 21),
    "CCDS": (3858 + 1385 + 655),
    "Science": (3312 + 1088 + 648),
    "HASS": (4333 + 1719 + 366),
    "Eng": (8943 + 6052 + 1412),
    "NBS": (3505 + 1698 + 79),
    "RSIS": (260 + 32),
    "NTU-SAF": 128,
}


EDU_HIGHER_ED = [
    Campus(
        name_short="NUS West",
        name="National University of Singapore (West)",
        students=(5769 + 5980) + (225 + 33) + 888 / 2,
        coord=Point(103.771609, 1.299291),
        institution="NUS",
        notes="CDE + YSTCM + 1/2 CompEng",
    ),
    Campus(
        name_short="NUS South",
        name="National University of Singapore (South)",
        students=(4006 + 1972) + (4024 + 2648) + (5460 + 1804) + 888 / 2,
        coord=Point(103.773240, 1.294167),
        institution="NUS",
        notes="FASS + Biz + SoC + 1/2 CompEng",
    ),
    Campus(
        name_short="NUS North",
        name="National University of Singapore (North)",
        students=(5767 + 3732) + (2567 + 1911) + (329 + 85),
        coord=Point(103.780257, 1.295989),
        institution="NUS",
        notes="FoS + MD + Dentistry",
    ),
    Campus(
        name_short="NUS UTown",
        name="National University of Singapore (UTown)",
        students=(996 + 320),
        coord=Point(103.772875, 1.305788),
        institution="NUS",
        notes="Law",
    ),
    # NTU splits: undergrad; graduate between coursework and research; grad diploma
    Campus(
        name_short="NIE",
        name="National Institute of Education",
        students=(632 + 1163 + 155 + 821),
        coord=Point(103.678617, 1.349115),
    ),
    Campus(
        name_short="NTU North",
        name="Nanyang Technical University (North)",
        students=_ntu_facs["Med"]
        + _ntu_facs["CCDS"]
        + _ntu_facs["Science"] / 2
        + _ntu_facs["HASS"] / 2
        + 2 * _ntu_facs["Eng"] / 3,
        coord=Point(103.680559, 1.346414),
        institution="NTU",
        notes="Med + CCDS + 1/2 Science (SBS) + 1/2 HASS + 2/3 Eng",
    ),
    Campus(
        name_short="NTU South",
        name="Nanyang Technical University (South)",
        students=_ntu_facs["NBS"]
        + _ntu_facs["Science"] / 2
        + _ntu_facs["RSIS"]
        + _ntu_facs["HASS"] / 2
        + _ntu_facs["Eng"] / 3
        + _ntu_facs["NTU-SAF"],
        coord=Point(103.681996, 1.342651),
        institution="NTU",
        notes="NBS + 1/2 Science (SPMS) + RSIS + 1/2 HASS + 1/3 Eng (EEE) + NTU-SAF Academy",
    ),
    Campus(
        name_short="SMU",
        name="Singapore Management University",
        students=9883 + 3166,
        coord=Point(103.849750, 1.295314),
    ),
    Campus(
        name_short="SUSS",
        name="Singapore University of Social Sciences",
        students=4000 + 1500,
        coord=Point(103.776217, 1.329413),
        notes="full time UG + PG",
    ),
    Campus(
        name_short="SIT",
        name="Singapore Institute of Technology",
        students=11571 + 278,
        coord=Point(103.911891, 1.413754),
    ),
    Campus(
        name_short="SUTD",
        name="Singapore University of Technology and Design",
        students=1969 + 699,
        coord=Point(103.962885, 1.340799),
        institution="SUTD",
    ),
    Campus(
        name_short="UAS LaSalle",
        name="University of the Arts Singapore (LaSalle)",
        students=2410,
        coord=Point(103.851590, 1.302834),
        institution="UAS",
    ),
    Campus(
        name_short="UAS NAFA",
        name="University of the Arts Singapore (NAFA)",
        students=2769,
        coord=Point(103.851407, 1.299748),
        institution="UAS",
    ),
    Campus(
        name_short="ITE College West",
        name="Institute of Technical Education College West",
        students=8000,
        coord=Point(103.751938, 1.375107),
        notes="full time students",
    ),
    Campus(
        name_short="ITE College Central",
        name="Institute of Technical Education College Central",
        students=(28096 - 8000) // 2,
        coord=Point(103.856289, 1.377946),
        notes="Subtracted from ITE West",
    ),
    Campus(
        name_short="ITE College East",
        name="Institute of Technical Education College East",
        students=(28096 - 8000) // 2,
        coord=Point(103.954520, 1.334639),
        notes="Subtracted from ITE West",
    ),
    Campus(
        name_short="SP",
        name="Singapore Polytechnic",
        students=12508,
        coord=Point(103.777987, 1.309754),
    ),
    Campus(
        name_short="NP",
        name="Ngee Ann Polytechnic",
        students=12578,
        coord=Point(103.774876, 1.332888),
    ),
    Campus(
        name_short="TP",
        name="Temasek Polytechnic",
        students=12546,
        coord=Point(103.932549, 1.345311),
    ),
    Campus(
        name_short="NYP",
        name="Nanyang Polytechnic",
        students=12787,
        coord=Point(103.849023, 1.380093),
    ),
    Campus(
        name_short="RP",
        name="Republic Polytechnic",
        students=11866,
        coord=Point(103.785122, 1.444390),
    ),
]
