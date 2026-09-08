import json
import re

from bs4 import BeautifulSoup

"""
What this script does:

It takes in the HTML source for the Wikipedia article about the list of Singapore Armed Forces military bases, scrapes 
it,and outputs a JSON representing the units at each base, 
for integration into Subway Builder mapping of my Singapore map.

The JSON will also include fields for manual entry of the applicable OSM object, as well as the lat/lon of the base's
main entry (or wherever I think the demand point should be situated.)
"""

# html file accessed: 2026-08-17
HTML_SRC_FILEPATH = r"List of Singapore Armed Forces bases - Wikipedia.html"

with open(HTML_SRC_FILEPATH) as fp:
    soup = BeautifulSoup(fp, features="html.parser")

bases_data = []


def create_base_dict(name: str, branch: str, unit_list: list[str]):
    return {
        "name": name,
        "branch": branch,
        "unit_count": len(unit_list),
        "units": unit_list,
        "osm_id": 0,
        "lat": 0,
        "lon": 0,
    }


for section in soup.find_all("section"):
    # aria-labelledby
    if "aria-labelledby" not in section.attrs:
        continue

    if not re.compile(r"(?:Army|Navy|Air_Force)").search(
        section.attrs["aria-labelledby"]
    ):
        continue

    # actual string looks like `Republic_of_Singapore_Air_Force_bases`
    section_name = section.attrs["aria-labelledby"].lower().replace("_", " ")
    if "army" in section_name:
        branch = "army"
    elif "navy" in section_name:
        branch = "navy"
    elif "air force" in section_name:
        branch = "airforce"
    else:
        branch = "unknown"


    table = section.find("table")
    assert table, "table not found in matching section"

    assert table.tbody, "table does not follow expected format (no tbody)"

    for row in table.tbody.find_all("tr"):
        # print(row)
        # print(".......................")
        row_children = list(row.find_all("td"))
        base_tag = row_children[0]
        units_tag = row_children[-1]

        def proces_unit_listitem(li) -> str:
            string_list = []

            for child in li.children:
                # sup = citation -> ignore
                if child.name == "sup":
                    continue

                string_list.append(child.string if child.string else "")

            return "".join(string_list)

        units_list = [proces_unit_listitem(li) for li in units_tag.find_all("li")]

        bases_data.append(
            create_base_dict(
                name=base_tag.string,
                branch=branch,
                unit_list=units_list,
            )
        )

OUTPUT_FILEPATH = "bases.json"

with open(OUTPUT_FILEPATH, "w") as f:
    json.dump(bases_data, fp=f, indent=4, ensure_ascii=False)