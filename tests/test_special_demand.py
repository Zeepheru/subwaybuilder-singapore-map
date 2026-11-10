import json
import unittest
from copy import copy

import geopandas as gpd
import numpy as np
import pandas as pd
from geopandas.testing import assert_geodataframe_equal
from shapely.geometry import Point

from src.data_manual.airports import AIRPORTS
from src.utils.population_distribution import build_demand_data, distribute_population
from src.utils.special_demand import (
    airport_destinations,
    distribute_airport_demand,
    hotel_origins,
    merge_origin_points,
    residential_population_origins,
)


class SpecialDemandTests(unittest.TestCase):
    def base(self):
        return gpd.GeoDataFrame(
            {"residents": [100, 300], "workers": [300, 100],
             "pln_area_id": ["A", "A"], "pln_region_id": ["R", "R"]},
            geometry=[Point(0, 0), Point(1000, 0)], index=["p_0", "p_1"], crs=3414,
        )

    def destinations(self, demand=1050, share=0.5):
        return gpd.GeoDataFrame(
            {"daily_demand": [demand], "hotel_share": [share]},
            geometry=[Point(500, 0)], index=["AIR_SIN_Terminal_1"], crs=3414,
        )

    def weights(self):
        return pd.DataFrame({
            "point_id": ["p_0", "p_1", "p_0", "p_1"],
            "pool_id": ["existing_residential", "existing_residential", "hotel", "hotel"],
            "population_weight": [100, 300, 300, 100],
        })

    def test_manual_airport_totals_and_capacity_split(self):
        destinations = airport_destinations(AIRPORTS, {"SIN": 0.5, "XSP": 0.5})
        self.assertEqual(len(destinations), 5)
        self.assertEqual(destinations.crs.to_epsg(), 3414)
        self.assertAlmostEqual(destinations.loc[destinations.index.str.startswith("AIR_SIN_"), "daily_demand"].sum(), 23000000 / 365)
        self.assertEqual(destinations.loc["AIR_XSP_Terminal", "daily_demand"], 400)
        self.assertAlmostEqual(destinations.loc["AIR_SIN_Terminal_1", "daily_demand"] / destinations.loc["AIR_SIN_Terminal_2", "daily_demand"], 24 / 28)
        self.assertEqual(destinations.loc["AIR_XSP_Terminal", "name"], "XSP Terminal")
        self.assertEqual(destinations.index.tolist(), [
            "AIR_SIN_Terminal_1", "AIR_SIN_Terminal_2", "AIR_SIN_Terminal_3",
            "AIR_SIN_Terminal_4", "AIR_XSP_Terminal",
        ])
        reordered = copy(AIRPORTS[0])
        reordered.terminals = list(reversed(reordered.terminals))
        actual = airport_destinations([reordered, AIRPORTS[1]], {"SIN": 0.5, "XSP": 0.5})
        assert_geodataframe_equal(actual.sort_index(), destinations.sort_index())

    def test_residential_population_conservation_and_zero_workforce_fallback(self):
        buildings = gpd.GeoDataFrame(
            {"subzone_id": ["A", "A", "B", "B"], "residents": [1, 3, 0, 0],
             "floorspace": [100, 100, 100, 300], "demand_type": ["res_med"] * 4},
            geometry=[Point(i, 0) for i in range(4)], crs=3414,
        )
        totals = pd.DataFrame({"res_pop_residence": [100, 200]}, index=["A", "B"])
        origins, report = residential_population_origins(buildings, totals, {"res_med": 1})
        np.testing.assert_array_equal(origins.population_weight, [25, 75, 50, 150])
        self.assertAlmostEqual(report.unallocated.sum(), 0)
        totals.loc["C"] = 50
        origins, report = residential_population_origins(buildings, totals, {"res_med": 1})
        self.assertEqual(report.loc["C", "unallocated"], 50)
        self.assertEqual(origins.population_weight.sum(), 300)

    def test_merge_preserves_base_membership_weights_and_distant_hotels(self):
        base = self.base()
        original = base.copy(deep=True)
        sources = gpd.GeoDataFrame(
            {"pool_id": ["existing_residential", "hotel", "hotel", "hotel"],
             "population_weight": [100, 50, 20, 30],
             "base_point_id": ["p_1", None, None, None]},
            geometry=[Point(0, 0), Point(10, 0), Point(5000, 0), Point(5050, 0)],
            index=["r", "h1", "h2", "h3"], crs=3414,
        )
        sources.index.name = "point_id"  # locate_demand_points names this index.
        registry, weights, membership = merge_origin_points(base, sources)
        assert_geodataframe_equal(base, original)
        pd.testing.assert_series_equal(registry.loc[base.index].geometry, base.geometry)
        mapping = membership.set_index("source_id").point_id
        self.assertEqual(mapping["r"], "p_1")  # Actual aggregation overrides proximity.
        self.assertEqual(mapping["h1"], "p_0")
        self.assertEqual(mapping["h2"], mapping["h3"])
        self.assertNotIn(mapping["h2"], base.index)
        self.assertEqual(weights.groupby("pool_id").population_weight.sum().to_dict(), {"existing_residential": 100, "hotel": 100})
        other_registry, other_weights, other_membership = merge_origin_points(base, sources.iloc[::-1])
        assert_geodataframe_equal(registry, other_registry)
        pd.testing.assert_frame_equal(weights, other_weights)
        pd.testing.assert_frame_equal(membership, other_membership)

    def test_merge_ties_empty_base_and_empty_origins(self):
        sources = gpd.GeoDataFrame(
            {"pool_id": ["hotel"], "population_weight": [1]},
            geometry=[Point(500, 0)], index=["h"], crs=3414,
        )
        _, _, mapping = merge_origin_points(self.base(), sources, radius=600)
        self.assertEqual(mapping.iloc[0].point_id, "p_0")
        registry, _, _ = merge_origin_points(self.base().iloc[:0], sources)
        self.assertEqual(len(registry), 1)
        registry, weights, membership = merge_origin_points(self.base(), sources.iloc[:0])
        self.assertEqual(len(registry), 2)
        self.assertTrue(weights.empty and membership.empty)

    def test_hotel_extraction_keeps_only_relative_hotel_weights(self):
        buildings = gpd.GeoDataFrame(
            {"demand_type": ["hotel", "commercial"], "floorspace": [123, 456]},
            geometry=[Point(0, 0), Point(0, 0)], crs=3414,
        )
        hotels = hotel_origins(buildings)
        self.assertEqual(hotels.index.tolist(), ["hotel:0"])
        self.assertEqual(hotels.population_weight.tolist(), [123])

    def test_rounding_splits_and_combined_export_preserve_workforce(self):
        base = self.base()
        allocated, workforce, quotas = distribute_population(base, pd.DataFrame({"R": [1]}, index=["A"]))
        original = allocated.copy(deep=True)
        registry, special, report = distribute_airport_demand(allocated, self.weights(), self.destinations(demand=1065))
        assert_geodataframe_equal(allocated, original)
        self.assertEqual(special["size"].sum(), 1050)
        self.assertEqual(report.allocated.tolist(), [550, 500])
        self.assertAlmostEqual(report.rounding_delta.sum(), -15)
        self.assertTrue(special["size"].isin([50, 200]).all())
        self.assertIn(200, special["size"].tolist())
        combined = pd.concat([workforce, special], ignore_index=True)
        payload = build_demand_data(registry, combined)
        json.dumps(payload, allow_nan=False)
        self.assertEqual(sum(p["jobs"] for p in payload["points"]), 1450)
        self.assertEqual(sum(p["residents"] for p in payload["points"]), 1450)
        self.assertEqual(len(set(p["id"] for p in payload["pops"])), len(combined))
        self.assertEqual(sum(p["size"] for p in payload["pops"] if not p["id"].startswith("special:")), quotas.to_numpy().sum())

    def test_seed_destination_order_and_geographic_reproducibility(self):
        destinations = self.destinations()
        second = self.destinations(600).rename(index={"AIR_SIN_Terminal_1": "AIR_XSP_Terminal"})
        second.geometry = [Point(1500, 0)]
        destinations = gpd.GeoDataFrame(pd.concat([destinations, second]), geometry="geometry", crs=3414)
        _, a, _ = distribute_airport_demand(self.base(), self.weights(), destinations, seed=12)
        _, b, _ = distribute_airport_demand(self.base().to_crs(4326), self.weights(), destinations.iloc[::-1].to_crs(4326), seed=12)
        pd.testing.assert_frame_equal(a, b)

    def test_population_weighting_and_distance_decay(self):
        weights = self.weights().loc[lambda f: f.pool_id.eq("existing_residential")]
        # Equal distances and a large sample recover the 1:3 population ratio.
        _, pops, _ = distribute_airport_demand(self.base(), weights, self.destinations(500000, 0))
        fraction = pops.loc[pops.residenceId.eq("p_1"), "size"].sum() / pops["size"].sum()
        self.assertAlmostEqual(fraction, 0.75, delta=0.02)
        destinations = self.destinations(5000, 0)
        destinations.geometry = [Point(0, 0)]
        _, pops, _ = distribute_airport_demand(self.base(), weights, destinations, distance_scale=1)
        self.assertTrue(pops.residenceId.eq("p_0").all())

    def test_zero_missing_pools_and_invalid_input(self):
        residential = self.weights().loc[lambda f: f.pool_id.eq("existing_residential")]
        with self.assertRaisesRegex(ValueError, "no positive hotel"):
            distribute_airport_demand(self.base(), residential, self.destinations())
        _, pops, _ = distribute_airport_demand(self.base(), residential, self.destinations(0))
        self.assertTrue(pops.empty)
        _, pops, _ = distribute_airport_demand(self.base(), residential, self.destinations(50, 0))
        self.assertEqual(pops["size"].sum(), 50)
        for kwargs in [{"small_size": 0}, {"large_size": 125}, {"distance_scale": float("nan")}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                distribute_airport_demand(self.base(), self.weights(), self.destinations(), **kwargs)
        for field, value in [("daily_demand", -1), ("hotel_share", 1.1), ("daily_demand", float("nan"))]:
            destinations = self.destinations()
            destinations[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                distribute_airport_demand(self.base(), self.weights(), destinations)
        with self.assertRaisesRegex(ValueError, "hotel share"):
            airport_destinations(AIRPORTS, {})


if __name__ == "__main__":
    unittest.main()
