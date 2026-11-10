import geopandas as gpd


def merge_building_parts_into_buildings(
    b_gdf: gpd.GeoDataFrame,
    bp_gdf: gpd.GeoDataFrame,
    debug: bool = False,
):
    """
    Adds the floorspace of building parts into buildings, so building parts do not need to be
    considered anymore for demand calculation

    `b_gdf`, `bp_gdf` should be the overall GDFs (the result after prior building removals),
    no specific selection of buildings with associated parts should be made.

    This will then modify existing buildings' `num_floors` based on the summation of floorspace
    of its constituent parts. Parts with `num_floors` are counted, with missing counts estimated from `height`
    at 3.6 metres per floor. Missing minimum floors default to zero. If no parts
    contribute positive floorspace, the original building floor count is preserved,
    including missing values so downstream estimation can still run.

    For buildings that have existing `num_floors`, this can point to two reasons:
    * (The correct OSM way) - the building's floor count refers to the max/min floors of a building.
        This is quite rare in Singapore, and is easily filtered out by checking max floors of a building
        against its parts. If the parent count is at least the maximum of its parts,
        its above-ground floorspace is taken entirely from its parts.
    * The more common tagging method in Singapore is for the building to represent some kind of lower-level
        structure, such as a carpark, or commercial building, underneath apartment tower blocks.
        To account for this, building parts will add onto the base building's num_floors.
        Of course, there are yet more asterisks because *most* building_parts don't get correctly tagged with
        minimum floors and as such vertically overlap. But I will not handle that. A notable example where
        this problem does crop up is *Suntec Tower 1*.
    """

    bp_gdf = bp_gdf.copy()
    # recalculate areas just in case
    bp_gdf["area"] = bp_gdf.area

    # select buildings with parts
    b_gdf = b_gdf.copy()
    b_gdf_withparts = b_gdf[b_gdf.index.isin(bp_gdf["building_id"])][
        ["num_floors", "min_floor", "area", "has_parts"]
    ]
    assert b_gdf_withparts[
        "has_parts"
    ].all(), "There are buildings in b_gdf with has_parts=False"

    # add floor counts to bparts without floors but with height
    # set min_height as min_floor as well
    mask = bp_gdf["num_floors"].isna() & ~bp_gdf["height"].isna()
    bp_gdf.loc[mask, "num_floors"] = (bp_gdf.loc[mask, "height"]) / 3.6
    min_floor_mask = mask & bp_gdf["min_floor"].isna()
    bp_gdf.loc[min_floor_mask, "min_floor"] = (
        bp_gdf.loc[min_floor_mask, "min_height"] / 3.6
    )

    bp_gdf["net_floors"] = (
        bp_gdf["num_floors"] - bp_gdf["min_floor"].fillna(0)
    ).clip(lower=0)
    floors_times_area = bp_gdf["net_floors"] * bp_gdf["area"]
    agg = floors_times_area.groupby(bp_gdf["building_id"]).sum(min_count=1)

    if debug:
        debug_parts = bp_gdf[
            bp_gdf["building_id"].eq("5634cc16-96d5-4f75-89b9-e4145da90bf3")
        ]
        if not debug_parts.empty:
            print("Parent building id:" + debug_parts.iloc[0]["building_id"])
            print(debug_parts[["area", "num_floors", "min_floor"]])
            print(agg.loc[debug_parts.iloc[0]["building_id"]])

    b_gdf_withparts["extra_floors_times_area"] = agg.reindex(
        b_gdf_withparts.index
    ).fillna(0)

    # Only merge parts that contribute floorspace. In particular, unknown parent
    # floors plus unknown part floors must stay unknown, rather than become zero.
    has_floorspace = b_gdf_withparts["extra_floors_times_area"].gt(0)
    buildings_to_update = b_gdf_withparts.loc[has_floorspace].copy()

    if buildings_to_update.empty:
        return b_gdf

    # Compare after estimating floors from height, so those parts participate too.
    parts_max_floors = bp_gdf.groupby("building_id")["num_floors"].max()
    replace_parent = buildings_to_update["num_floors"].isna() | (
        buildings_to_update["num_floors"].ge(
            parts_max_floors.reindex(buildings_to_update.index)
        )
    )
    # Parts already have their minimum floors subtracted. The caller subtracts
    # the parent's min_floor later, so retain that offset when replacing its floors.
    base_floors = buildings_to_update["num_floors"].where(
        ~replace_parent, buildings_to_update["min_floor"].fillna(0)
    )
    b_gdf.update(
        {
            "num_floors": base_floors
            + buildings_to_update["extra_floors_times_area"]
            / buildings_to_update["area"]
        }
    )
    return b_gdf
