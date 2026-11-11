import json
import unittest

import geopandas as gpd
import numpy as np
import pandas as pd
from geopandas.testing import assert_geodataframe_equal
from shapely.geometry import Point

from src.data_manual.education_higher import Campus, EDU_HIGHER_ED
from src.utils.population_distribution import build_demand_data
from src.utils.special_demand import (
    distribute_airport_demand,
    distribute_special_demand,
    university_destinations,
)


class UniversityDemandTests(unittest.TestCase):
    def points(self):
        return gpd.GeoDataFrame(
            {"residents": [100, 300, 0], "workers": [300, 100, 0]},
            geometry=[Point(0, 0), Point(1000, 0), Point(500, 0)],
            index=["p_0", "p_1", "hotel_only"], crs=3414,
        )

    def weights(self):
        return pd.DataFrame({
            "point_id": ["p_0", "p_1", "hotel_only"],
            "pool_id": ["existing_residential", "existing_residential", "hotel"],
            "population_weight": [100, 100, 100000],
        })

    def destinations(self, university=1015, airport=1050):
        return gpd.GeoDataFrame(
            {"category": ["airport", "university"],
             "daily_demand": [airport, university], "hotel_share": [0.5, 0]},
            geometry=[Point(0, 0), Point(0, 0)],
            index=["AIR_TEST", "UNI_TEST"], crs=3414,
        )

    def test_higher_education_source_counts_ids_and_metadata(self):
        destinations = university_destinations(EDU_HIGHER_ED)
        self.assertEqual(len(destinations), 21)
        self.assertEqual(destinations.crs.to_epsg(), 3414)
        self.assertIn("UNI_NUS_West", destinations.index)
        self.assertIn("UNI_ITE_College_West", destinations.index)
        self.assertEqual(destinations.loc["UNI_NUS_West", "institution"], "NUS")
        self.assertEqual(destinations.loc["UNI_NUS_West", "notes"], EDU_HIGHER_ED[0].notes)
        self.assertTrue(destinations.hotel_share.eq(0).all())
        self.assertTrue(destinations.category.eq("university").all())
        self.assertAlmostEqual(destinations.daily_demand.sum(), sum(c.students for c in EDU_HIGHER_ED))
        reordered = university_destinations(list(reversed(EDU_HIGHER_ED)))
        assert_geodataframe_equal(destinations.sort_index(), reordered.sort_index())

    def test_additive_residential_only_allocation_rounding_and_schema(self):
        points, weights = self.points(), self.weights()
        original = points.copy(deep=True)
        original_weights = weights.copy(deep=True)
        registry, pops, report = distribute_special_demand(
            points, weights, self.destinations(), {"airport": 10000, "university": 5000},
        )
        assert_geodataframe_equal(points, original)
        pd.testing.assert_frame_equal(weights, original_weights)
        assert_geodataframe_equal(registry.loc[points.index], points, check_dtype=False)
        university = pops.loc[pops.category.eq("university")]
        self.assertEqual(university["size"].sum(), 1000)
        self.assertTrue(university.pool_id.eq("existing_residential").all())
        self.assertTrue(university.residenceId.isin(["p_0", "p_1"]).all())
        self.assertTrue(university.jobId.eq("UNI_TEST").all())
        self.assertTrue(university["size"].isin([50, 200]).all())
        uni_report = report.loc[report.category.eq("university")]
        self.assertEqual(uni_report.pool_id.tolist(), ["existing_residential"])
        self.assertEqual(uni_report.rounding_delta.tolist(), [-15])
        self.assertEqual(uni_report.distance_scale.tolist(), [5000])
        payload = build_demand_data(registry, pops)
        json.dumps(payload, allow_nan=False)
        self.assertEqual(sum(p["residents"] for p in payload["points"]), 2050)
        self.assertEqual(sum(p["jobs"] for p in payload["points"]), 2050)
        self.assertEqual(len(set(p["id"] for p in payload["pops"])), len(pops))
        # Adding universities retains the airport-only groups and allocations.
        _, airport_only, _ = distribute_airport_demand(points, weights, self.destinations().iloc[:1])
        pd.testing.assert_frame_equal(pops.loc[pops.category.eq("airport")].reset_index(drop=True), airport_only)

    def test_class_specific_decay_and_reproducibility(self):
        destinations = self.destinations(university=500000, airport=500000)
        destinations["hotel_share"] = 0
        scales = {"airport": 1, "university": 1e12}
        _, a, report = distribute_special_demand(self.points(), self.weights(), destinations, scales)
        _, b, _ = distribute_special_demand(
            self.points(), self.weights(), destinations.iloc[::-1], scales,
        )
        pd.testing.assert_frame_equal(a, b)
        airport = a.loc[a.category.eq("airport")]
        self.assertTrue(airport.residenceId.eq("p_0").all())
        university = a.loc[a.category.eq("university")]
        far_share = university.loc[university.residenceId.eq("p_1"), "size"].sum() / 500000
        self.assertAlmostEqual(far_share, 0.5, delta=0.02)
        _, changed, _ = distribute_special_demand(
            self.points(), self.weights(), destinations, {"airport": 1, "university": 1},
        )
        self.assertTrue(changed.loc[changed.category.eq("university"), "residenceId"].eq("p_0").all())
        pd.testing.assert_frame_equal(airport, changed.loc[changed.category.eq("airport")])
        self.assertEqual(report.groupby("category").distance_scale.first().to_dict(), scales)

    def test_missing_scales_invalid_scales_and_unsupported_housing_split(self):
        for scales in [{"airport": 10000}, {"airport": 0, "university": 10000},
                       {"airport": 10000, "university": np.nan},
                       {"airport": 10000, "university": np.inf}]:
            with self.subTest(scales=scales), self.assertRaises(ValueError):
                distribute_special_demand(self.points(), self.weights(), self.destinations(), scales)
        destinations = self.destinations()
        destinations.loc["UNI_TEST", "hotel_share"] = 0.5
        with self.assertRaisesRegex(ValueError, "only existing residential"):
            distribute_special_demand(
                self.points(), self.weights(), destinations, {"airport": 10000, "university": 10000},
            )

    def test_university_zero_and_missing_residential_origins(self):
        destinations = self.destinations(university=0).iloc[1:]
        _, pops, _ = distribute_special_demand(
            self.points(), self.weights(), destinations, {"university": 10000},
        )
        self.assertTrue(pops.empty)
        destinations["daily_demand"] = 100
        with self.assertRaisesRegex(ValueError, "no positive existing_residential"):
            distribute_special_demand(
                self.points(), self.weights().iloc[2:], destinations, {"university": 10000},
            )

    def test_large_first_maximizes_large_groups_per_destination_pool(self):
        # A dispersed origin pool exposes the fragmentation from small-first draws.
        points = gpd.GeoDataFrame(
            {"residents": [100] * 100 + [0], "workers": [0] * 101},
            geometry=[Point(0, 0)] * 101,
            index=[f"p_{i}" for i in range(100)] + ["hotel_only"], crs=3414,
        )
        weights = pd.DataFrame({
            "point_id": points.index,
            "pool_id": ["existing_residential"] * 100 + ["hotel"],
            "population_weight": [1] * 101,
        })
        destinations = self.destinations(university=10115, airport=1550)
        scales = {"airport": 10000, "university": 10000}
        for small, large in [(50, 200), (25, 100), (50, 400)]:
            with self.subTest(small=small, large=large):
                _, pops, report = distribute_special_demand(
                    points, weights, destinations, scales, small_size=small, large_size=large,
                )
                for row in report.itertuples():
                    groups = pops.loc[pops.jobId.eq(row.destination_id) & pops.pool_id.eq(row.pool_id)]
                    self.assertEqual(groups["size"].sum(), row.allocated)
                    self.assertEqual(groups["size"].eq(large).sum(), row.allocated // large)
                    self.assertEqual(groups["size"].eq(small).sum(), (row.allocated % large) // small)
                    self.assertLess(groups["size"].eq(small).sum(), large // small)
                    self.assertEqual(row.group_allocation_mode, "large_first")
                _, legacy, old_report = distribute_special_demand(
                    points, weights, destinations, scales, small_size=small, large_size=large,
                    group_allocation_modes={"airport": "small_first", "university": "small_first"},
                )
                self.assertLess(pops["size"].eq(small).sum(), legacy["size"].eq(small).sum())
                pd.testing.assert_frame_equal(
                    report.drop(columns="group_allocation_mode"),
                    old_report.drop(columns="group_allocation_mode"),
                )

    def test_group_modes_are_per_class_and_legacy_airport_interface_supports_them(self):
        destinations = self.destinations(university=1015, airport=1050)
        scales = {"airport": 10000, "university": 10000}
        modes = {"airport": "small_first", "university": "large_first"}
        _, mixed, report = distribute_special_demand(
            self.points(), self.weights(), destinations, scales, group_allocation_modes=modes,
        )
        _, repeated, _ = distribute_special_demand(
            self.points(), self.weights(), destinations.iloc[::-1], scales,
            group_allocation_modes=modes,
        )
        pd.testing.assert_frame_equal(mixed, repeated)
        _, airport, _ = distribute_airport_demand(
            self.points(), self.weights(), destinations.iloc[:1], group_allocation_mode="small_first",
        )
        pd.testing.assert_frame_equal(mixed.loc[mixed.category.eq("airport")].reset_index(drop=True), airport)
        self.assertEqual(report.groupby("category").group_allocation_mode.first().to_dict(), modes)
        university = mixed.loc[mixed.category.eq("university")]
        self.assertEqual(university["size"].sum(), 1000)
        self.assertTrue(university["size"].eq(200).all())

    def test_large_first_remainders_and_invalid_modes(self):
        for demand in [0, 50, 150, 200, 250, 350]:
            with self.subTest(demand=demand):
                _, pops, _ = distribute_special_demand(
                    self.points(), self.weights(), self.destinations(university=demand).iloc[1:],
                    {"university": 10000},
                )
                self.assertEqual(pops["size"].sum(), demand)
                self.assertEqual(pops["size"].eq(200).sum(), demand // 200)
                self.assertEqual(pops["size"].eq(50).sum(), (demand % 200) // 50)
        for modes in [{"university": "large_first"},
                      {"airport": "random", "university": "large_first"},
                      {"airport": "large_first", "university": None}]:
            with self.subTest(modes=modes), self.assertRaises(ValueError):
                distribute_special_demand(
                    self.points(), self.weights(), self.destinations(),
                    {"airport": 10000, "university": 10000}, group_allocation_modes=modes,
                )

    def test_campus_validation_and_empty_input(self):
        self.assertTrue(university_destinations([]).empty)
        for count in [-1, np.nan, np.inf]:
            with self.subTest(students=count), self.assertRaises(ValueError):
                university_destinations([Campus("Test", "TEST", count, Point(103.8, 1.3))])
        with self.assertRaises(ValueError):
            university_destinations([Campus("Test", "  ", 100, Point(103.8, 1.3))])
        with self.assertRaisesRegex(ValueError, "unique"):
            university_destinations([Campus("A", "Test Campus", 10, Point(103.8, 1.3)),
                                     Campus("B", "Test_Campus", 10, Point(103.8, 1.3))])


if __name__ == "__main__":
    unittest.main()
