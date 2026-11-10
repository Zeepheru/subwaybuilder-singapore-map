from typing import Literal

import numpy as np
from shapely import Point


class Hospital:

    def __init__(
        self,
        name: str,
        name_short: str = None,
        workforce: int = np.nan,
        beds: int = np.nan,
        inpatient: int = np.nan,
        outpatient: int = np.nan,
        group: str = None,
        hosp_funding: Literal["private", "public", "nonprofit"] = "private",
        healthcare_type: Literal[
            "acute", "community", "primary", "psychiatric", "nursing_home", "unknown"
        ] = "unknown",
        plot_ids: list[int] = [],
        notes: str = "",
    ):
        self.name = name
        self.name_short = name_short
        self.workforce = workforce
        self.beds = beds
        self.inpatient = inpatient
        self.outpatient = outpatient
        self.group = group
        self.hosp_funding = hosp_funding
        self.healthcare_type = healthcare_type
        self.plot_ids = plot_ids
        self.notes = notes

    @property
    def dict(self):
        return {
            "name": self.name,
            "name_short": self.name_short,
            "workforce": self.workforce,
            "beds": self.beds,
            "inpatient": self.inpatient,
            "outpatient": self.outpatient,
            "group": self.group,
            "hosp_funding": self.hosp_funding,
            "healthcare_type": self.healthcare_type,
            "plot_ids": self.plot_ids,
            "notes": self.notes,
        }


HOSPITALS = [
    Hospital(
        name="Changi General Hospital",
        name_short="CGH",
        workforce=7092,
        beds=1132,
        group="SH",
        hosp_funding="public",
        healthcare_type="acute",
        plot_ids=[682287, 680004],
    ),
    Hospital(
        name="Sengkang General Hospital",
        name_short="SKH",
        workforce=5404 + 575,
        beds=920 + 400,
        group="SH",
        hosp_funding="public",
        healthcare_type="acute",
        plot_ids=[695425],
        notes="Includes SCH",
    ),
    Hospital(
        name="KK Women's and Children's Hospital",
        name_short="KKH",
        workforce=5411,
        beds=864,
        group="SH",
        hosp_funding="public",
        healthcare_type="acute",
        plot_ids=[624654],
    ),
    Hospital(
        name="Outram Community Hospital",
        name_short="OCH",
        workforce=724,
        beds=382,
        group="SH",
        hosp_funding="public",
        healthcare_type="community",
        plot_ids=[682291],
    ),
    Hospital(
        name="Singapore General Hospital",
        name_short="SGH",
        workforce=10725,
        beds=1931,
        group="SH",
        hosp_funding="public",
        healthcare_type="acute",
        plot_ids=[678888],
    ),
    Hospital(
        name="SingHealth Outram Specialist Centres",
        workforce=1537 + 579 + 1369 + 513 + 1085,
        beds=185,
        group="SH",
        hosp_funding="public",
        healthcare_type="acute",
        plot_ids=[640109],
        notes="NCCS + NDCS + NHCS + NNI + SNEC",
    ),
    Hospital(
        name="Tan Tock Seng Hospital",
        name_short="TTSH",
        beds=1700,
        group="NHG",
        hosp_funding="public",
        healthcare_type="acute",
        plot_ids=[680770, 655353, 637477, 656226, 641573, 629321, 629321, 613732],
        notes="includes NCID + NSC + ICH, not that I have numbers anyway",
    ),
    Hospital(
        name="Khoo Teck Puat Hospital",
        name_short="KTPH",
        beds=795 + 224,
        group="NHG",
        hosp_funding="public",
        healthcare_type="acute",
        plot_ids=[671348, 632466],
        notes="Includes YCH",
    ),
    Hospital(
        name="Woodlands Hospital",
        name_short="WH",
        beds=1800,
        group="NHG",
        hosp_funding="public",
        healthcare_type="acute",
        plot_ids=[688804],
        notes="Includes WH-CH",
    ),
    Hospital(
        name="Institute of Mental Health",
        name_short="IMH",
        beds=1950,
        group="NHG",
        hosp_funding="public",  # should have lower staff-bed ratio
        healthcare_type="psychiatric",
        plot_ids=[662035],
    ),
    Hospital(
        name="National University Hospital",
        name_short="NUH",
        workforce=10700,
        beds=1700,
        group="NUHS",
        hosp_funding="public",
        healthcare_type="acute",
        plot_ids=[656790],
    ),
    Hospital(
        name="Alexandra Hospital",
        name_short="AH",
        beds=326,
        group="NUHS",
        hosp_funding="public",
        healthcare_type="acute",
        plot_ids=[678590],
    ),
    Hospital(
        name="Ng Teng Fong General Hospital",
        name_short="NTFGH",
        beds=700 + 400,
        group="NUHS",
        hosp_funding="public",
        healthcare_type="acute",
        plot_ids=[613193, 610037],
        notes="Includes JCH",
    ),
    Hospital(
        name="Mount Alvernia Hospital",
        beds=319,
        hosp_funding="nonprofit",
        healthcare_type="acute",
        plot_ids=[670861],
    ),
    Hospital(
        name="Crawfurd Hospital",
        beds=31,
        hosp_funding="private",
        healthcare_type="acute",
        plot_ids=[615761],
    ),
    Hospital(
        name="Gleneagles Hospital",
        beds=257,
        group="IHH Healthcare",
        hosp_funding="private",
        healthcare_type="acute",
        plot_ids=[698382],
    ),
    Hospital(
        name="Mount Elizabeth Hospital",
        beds=345,
        group="IHH Healthcare",
        hosp_funding="private",
        healthcare_type="acute",
        plot_ids=[593446],
    ),
    Hospital(
        name="Mount Elizabeth Novena Hospital",
        beds=333,
        group="IHH Healthcare",
        hosp_funding="private",
        healthcare_type="acute",
        plot_ids=[678392],
    ),
    Hospital(
        name="Parkway East Hospital",
        beds=143,
        group="IHH Healthcare",
        hosp_funding="private",
        healthcare_type="acute",
        plot_ids=[623499],
    ),
    Hospital(
        name="Raffles Hospital",
        beds=380,
        group="Raffles Medical Group",
        hosp_funding="private",
        healthcare_type="acute",
        plot_ids=[637442],
    ),
    Hospital(
        name="Thomson Medical Centre",
        beds=187,
        group="Thomson Medical Group",
        hosp_funding="private",
        healthcare_type="acute",
        plot_ids=[688155],
    ),
    Hospital(
        name="Thye Hua Kwan Hospital",
        beds=360,
        hosp_funding="nonprofit",
        healthcare_type="community",
        plot_ids=[634995],
    ),
    Hospital(
        name="Ren Ci Community Hospital",
        beds=243,
        hosp_funding="nonprofit",
        healthcare_type="community",
        plot_ids=[666914],
        notes="bed count subtracted from its nursing homes",
    ),
    Hospital(
        name="St Andrew's Community Hospital",
        name_short="SACH",
        beds=277,
        hosp_funding="nonprofit",
        healthcare_type="community",
        plot_ids=[670142],
    ),
    Hospital(
        name="St Luke's Hospital",
        name_short="SLH",
        workforce=588,
        hosp_funding="nonprofit",
        healthcare_type="community",
        plot_ids=[611088],
    ),
]

# missing AdMC - not a high priority
# missing SACH (part of CGH campus, was not counted there)
# missing Farrer Park Hosp (small-medium private)
