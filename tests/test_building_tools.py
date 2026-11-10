import unittest

import geopandas as gpd
import pandas as pd
from geopandas.testing import assert_geodataframe_equal
from shapely.geometry import box

from src.utils.building_tools import merge_building_parts_into_buildings


class MergeBuildingPartsTests(unittest.TestCase):
    def merge(self, parent_floors, parts, parent_min=0):
        buildings = gpd.GeoDataFrame(
            {
                "num_floors": [parent_floors],
                "min_floor": [parent_min],
                "area": [100.0],
                "has_parts": [bool(parts)],
            },
            index=["parent"],
            geometry=[box(0, 0, 10, 10)],
            crs=3414,
        )
        part_rows = [
            {
                "building_id": "parent",
                "num_floors": float("nan"),
                "min_floor": float("nan"),
                "height": float("nan"),
                "min_height": float("nan"),
                "geometry": box(0, 0, 10, 10),
                **part,
            }
            for part in parts
        ]
        building_parts = gpd.GeoDataFrame(
            part_rows,
            columns=[
                "building_id", "num_floors", "min_floor", "height",
                "min_height", "geometry",
            ],
            geometry="geometry",
            crs=3414,
        )
        original_buildings = buildings.copy(deep=True)
        original_parts = building_parts.copy(deep=True)
        result = merge_building_parts_into_buildings(buildings, building_parts)
        assert_geodataframe_equal(buildings, original_buildings)
        assert_geodataframe_equal(building_parts, original_parts)
        return result.loc["parent", "num_floors"] - parent_min

    def test_missing_floors_remain_unknown_without_usable_parts(self):
        for parts in [
            [{}],
            [{"num_floors": 3, "min_floor": 3}],
            [{"num_floors": 3, "min_floor": 4}],
            [],
        ]:
            with self.subTest(parts=parts):
                self.assertTrue(pd.isna(self.merge(float("nan"), parts)))

    def test_existing_floors_survive_parts_without_floorspace(self):
        for parts in [[{}], [{"num_floors": 3, "min_floor": 3}], []]:
            with self.subTest(parts=parts):
                self.assertEqual(self.merge(5.0, parts), 5.0)

    def test_parts_replace_matching_parent_maximum(self):
        self.assertEqual(self.merge(10.0, [{"num_floors": 10}]), 10.0)

    def test_parts_add_to_lower_base_building(self):
        self.assertEqual(self.merge(2.0, [{"num_floors": 10, "min_floor": 2}]), 10.0)

    def test_height_estimates_participate_in_parent_comparison(self):
        self.assertAlmostEqual(self.merge(10.0, [{"height": 36}]), 10.0)

    def test_height_estimation_preserves_explicit_min_floor(self):
        self.assertAlmostEqual(
            self.merge(float("nan"), [{"height": 36, "min_floor": 2}]), 8.0
        )

    def test_height_estimation_uses_min_height_if_min_floor_missing(self):
        self.assertAlmostEqual(
            self.merge(float("nan"), [{"height": 36, "min_height": 7.2}]), 8.0
        )

    def test_parent_minimum_is_not_subtracted_twice(self):
        for parent_floors in [float("nan"), 10.0]:
            with self.subTest(parent_floors=parent_floors):
                self.assertEqual(
                    self.merge(parent_floors, [{"num_floors": 10, "min_floor": 5}], parent_min=5),
                    5.0,
                )

    def test_floor_counts_are_weighted_by_part_area(self):
        self.assertEqual(
            self.merge(float("nan"), [
                {"num_floors": 10, "geometry": box(0, 0, 5, 10)},
                {"num_floors": 4, "geometry": box(5, 0, 10, 10)},
            ]),
            7.0,
        )


if __name__ == "__main__":
    unittest.main()
