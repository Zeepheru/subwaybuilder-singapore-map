import json
import unittest

import geopandas as gpd
import numpy as np
import pandas as pd
from geopandas.testing import assert_geodataframe_equal
from shapely.geometry import Point, box

from src.utils.population_distribution import (
    build_demand_data,
    distribute_population,
    locate_demand_points,
)


class PopulationDistributionTests(unittest.TestCase):
    def points(self):
        return gpd.GeoDataFrame(
            {
                "residents": [650, 100, 0, 0],
                "workers": [0, 0, 500, 250],
                "pln_region_id": ["R1", "R2", "R1", "R2"],
                "pln_area_id": ["A", "B", "A", "B"],
            },
            geometry=[Point(0, 0), Point(100, 0), Point(1000, 0), Point(2000, 0)],
            index=["p_0", "p_1", "p_2", "p_3"],
            crs=3414,
        )

    def weights(self):
        return pd.DataFrame({"R1": [0.8, 0.2], "R2": [0.2, 0.8]}, index=["A", "B"])

    def test_conservation_schema_and_od_quotas(self):
        points = self.points()
        original = points.copy(deep=True)
        allocated, pops, quotas = distribute_population(points, self.weights())
        assert_geodataframe_equal(points, original)
        self.assertEqual(pops["size"].sum(), 750)
        for key, column in [("residenceId", "residents"), ("jobId", "workers")]:
            actual = pops.groupby(key)["size"].sum().reindex(allocated.index, fill_value=0)
            np.testing.assert_array_equal(actual, allocated[column])
        realized = pops.assign(
            area=pops["jobId"].map(points["pln_area_id"]),
            region=pops["residenceId"].map(points["pln_region_id"]),
        ).pivot_table(index="area", columns="region", values="size", aggfunc="sum", fill_value=0)
        np.testing.assert_array_equal(realized.reindex(index=quotas.index, columns=quotas.columns, fill_value=0), quotas)
        payload = build_demand_data(allocated, pops)
        json.dumps(payload, allow_nan=False)
        by_id = {point["id"]: point for point in payload["points"]}
        self.assertEqual(set(payload), {"points", "pops"})
        for point in by_id.values():
            self.assertEqual(set(point), {"id", "location", "jobs", "residents", "popIds"})
            self.assertIsInstance(point["jobs"], int)
            self.assertIsInstance(point["residents"], int)
            self.assertTrue(-180 <= point["location"][0] <= 180)
            self.assertTrue(-90 <= point["location"][1] <= 90)
            expected_ids = [p["id"] for p in payload["pops"] if point["id"] in (p["residenceId"], p["jobId"])]
            self.assertEqual(point["popIds"], expected_ids)
        for pop in payload["pops"]:
            self.assertEqual(set(pop), {"id", "size", "residenceId", "jobId", "drivingDistance", "drivingSeconds"})
            self.assertIsInstance(pop["drivingDistance"], int)
            self.assertEqual(pop["drivingSeconds"], int(points.geometry.loc[pop["residenceId"]].distance(points.geometry.loc[pop["jobId"]]) / (40 / 3.6)))

    def test_mixed_sizes_and_residuals(self):
        points = self.points()
        points["pln_region_id"] = "R1"
        points["pln_area_id"] = "A"
        _, pops, _ = distribute_population(points, pd.DataFrame({"R1": [1]}, index=["A"]))
        self.assertEqual(set(pops["size"]), {50, 200})
        self.assertTrue(pops.loc[pops["residenceId"] == "p_1", "size"].eq(50).all())

    def test_unequal_totals_are_balanced_without_losing_units(self):
        points = self.points()
        points["residents"] *= 2
        allocated, pops, _ = distribute_population(points, self.weights())
        self.assertEqual(allocated["residents"].sum(), 750)
        self.assertEqual(allocated["workers"].sum(), 750)
        self.assertTrue(allocated["residents"].mod(50).eq(0).all())
        self.assertEqual(pops["size"].sum(), 750)

    def test_seed_reproducibility_and_geographic_input(self):
        points = self.points()
        _, a, _ = distribute_population(points, self.weights(), seed=19)
        _, b, _ = distribute_population(points, self.weights(), seed=19)
        _, geographic, _ = distribute_population(points.to_crs(4326), self.weights(), seed=19)
        pd.testing.assert_frame_equal(a, b)
        pd.testing.assert_frame_equal(a, geographic)

    def test_distance_decay_favors_nearby_workplaces(self):
        points = self.points()
        points["residents"] = [100, 100, 0, 0]
        points["workers"] = [0, 0, 100, 100]
        points["pln_region_id"] = "R1"
        points["pln_area_id"] = "A"
        points.geometry = [Point(0, 0), Point(10000, 0), Point(1, 0), Point(10001, 0)]
        weights = pd.DataFrame({"R1": [1]}, index=["A"])
        def mean_distance(scale):
            _, pops, _ = distribute_population(points, weights, small_size=1, large_size=1000, distance_scale=scale)
            return sum(points.geometry.loc[p.residenceId].distance(points.geometry.loc[p.jobId]) * p.size for p in pops.itertuples()) / 200
        self.assertLess(mean_distance(10), mean_distance(1e9) / 10)

    def test_boundary_ties_unmatched_points_and_special_ids(self):
        points = gpd.GeoDataFrame(
            {"residents": [50, 50, 50], "workers": [50, 50, 50]},
            geometry=[Point(1, 1), Point(2, 1), Point(9, 9)],
            index=[0, "AIR_SIN", 2], crs=3414,
        )
        areas = gpd.GeoDataFrame(geometry=[box(0, 0, 2, 2), box(2, 0, 4, 2)], index=["B", "A"], crs=3414)
        regions = gpd.GeoDataFrame(geometry=[box(0, 0, 4, 4)], index=["R"], crs=3414)
        located = locate_demand_points(points, areas, regions)
        self.assertEqual(len(located), 3)
        self.assertEqual(located.loc["AIR_SIN", "pln_area_id"], "A")
        self.assertTrue(pd.isna(located.loc["p_2", "pln_region_id"]))

    def test_equal_distance_choices_are_population_weighted(self):
        points = self.points()
        points["residents"] = [100, 300, 0, 0]
        points["workers"] = [0, 0, 100, 300]
        points["pln_region_id"] = "R1"
        points["pln_area_id"] = "A"
        points.geometry = [Point(0, 0), Point(0, 0), Point(100, 0), Point(100, 0)]
        weights = pd.DataFrame({"R1": [1]}, index=["A"])
        origins, destinations = [], []
        for seed in range(100):
            _, pops, _ = distribute_population(points, weights, large_size=1000, seed=seed)
            origins.append(pops.iloc[0]["residenceId"] == "p_1")
            destinations.append(pops.iloc[0]["jobId"] == "p_3")
        # Equal distances give a 3:1 first-choice probability at each endpoint.
        for samples in (origins, destinations):
            self.assertGreater(np.mean(samples), 0.6)
            self.assertLess(np.mean(samples), 0.9)

    def test_empty_zero_and_self_commutes(self):
        points = self.points().iloc[:0]
        allocated, pops, _ = distribute_population(points, self.weights())
        self.assertEqual(build_demand_data(allocated, pops), {"points": [], "pops": []})
        points = self.points().iloc[:1].copy()
        points[["residents", "workers"]] = 100
        allocated, pops, _ = distribute_population(points, self.weights())
        payload = build_demand_data(allocated, pops)
        self.assertEqual(payload["points"][0]["popIds"], pops["id"].tolist())
        self.assertTrue(all(p["drivingDistance"] == 0 for p in payload["pops"]))
        points["workers"] = 0
        _, pops, _ = distribute_population(points, self.weights())
        self.assertTrue(pops.empty)

    def test_invalid_configuration_and_input(self):
        for options in [{"small_size": 0}, {"large_size": 125}, {"large_size": 50}, {"distance_scale": 0}, {"distance_scale": float("nan")}]:
            with self.subTest(options=options), self.assertRaises(ValueError):
                distribute_population(self.points(), self.weights(), **options)
        for column, value in [("residents", -1), ("workers", float("nan")), ("pln_area_id", None)]:
            points = self.points()
            points.loc["p_0", column] = value
            with self.subTest(column=column), self.assertRaises(ValueError):
                distribute_population(points, self.weights())
        with self.assertRaises(ValueError):
            distribute_population(self.points(), self.weights().drop(index="A"))
        with self.assertRaises(ValueError):
            distribute_population(self.points(), self.weights() * 0)


if __name__ == "__main__":
    unittest.main()
