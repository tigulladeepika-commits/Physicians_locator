import copy
import unittest
from unittest.mock import patch

import app as backend_app


def make_physician(npi: str, zip_code: str = "", lat=None, lng=None) -> dict:
    return {
        "npi": npi,
        "name": f"Doctor {npi}",
        "taxonomy_code": "",
        "taxonomy_desc": "Cardiology",
        "all_taxonomies": [],
        "address": "",
        "address_1": "123 Main St" if zip_code else "",
        "city": "Los Angeles",
        "state": "CA",
        "zip": zip_code,
        "phone": "",
        "lat": lat,
        "lng": lng,
        "distance_miles": None,
    }


class SearchRadiusTests(unittest.TestCase):
    def setUp(self):
        self.client = backend_app.app.test_client()

    def test_search_excludes_physicians_without_coordinates(self):
        parsed = {
            "1": make_physician("1"),
        }

        with patch("app.zip_database.wait_for_ready", return_value=True), \
             patch("app.zip_database.find_zips_in_radius", return_value=["11111"]), \
             patch("app.zip_database.get_zip_coords", return_value=(None, None)), \
             patch("app.zip_database.haversine", return_value=5.0), \
             patch("app.nppes.fetch_with_retry", return_value=([{"number": "1"}], 1)), \
             patch("app.nppes.parse_physician", side_effect=lambda raw: copy.deepcopy(parsed[raw["number"]])), \
             patch("app.nppes.batch_geocode_for_display"), \
             patch("app.nppes.apply_coord_jitter"):
            response = self.client.get(
                "/api/search?lat=34.05&lng=-118.24&radius=10",
                headers={"X-Forwarded-For": "10.0.0.1"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["total"], 0)
        self.assertEqual(payload["returned"], 0)
        self.assertEqual(payload["physicians"], [])

    def test_search_rechecks_display_results_with_exact_coordinates(self):
        parsed = {
            "1": make_physician("1", "11111"),
            "2": make_physician("2", "22222"),
        }

        coarse_coords = {
            "11111": (34.10, -118.24),
            "22222": (34.15, -118.24),
        }
        distances = {
            (34.10, -118.24): 5.0,
            (34.15, -118.24): 6.0,
            (34.30, -118.24): 15.0,
            (34.20, -118.24): 8.0,
        }

        def fetch_with_retry(params):
            postal_code = params.get("postal_code")
            if postal_code == "11111":
                return [{"number": "1"}], 1
            if postal_code == "22222":
                return [{"number": "2"}], 1
            return [], 0

        def batch_geocode_for_display(physicians):
            for physician in physicians:
                if physician["npi"] == "1":
                    physician["lat"], physician["lng"] = (34.30, -118.24)
                if physician["npi"] == "2":
                    physician["lat"], physician["lng"] = (34.20, -118.24)

        def haversine(_lat1, _lng1, lat2, lng2):
            return distances[(round(lat2, 2), round(lng2, 2))]

        with patch("app.zip_database.wait_for_ready", return_value=True), \
             patch("app.zip_database.find_zips_in_radius", return_value=["11111", "22222"]), \
             patch("app.zip_database.get_zip_coords", side_effect=lambda zipcode: coarse_coords[zipcode]), \
             patch("app.zip_database.haversine", side_effect=haversine), \
             patch("app.nppes.fetch_with_retry", side_effect=fetch_with_retry), \
             patch("app.nppes.parse_physician", side_effect=lambda raw: copy.deepcopy(parsed[raw["number"]])), \
             patch("app.nppes.batch_geocode_for_display", side_effect=batch_geocode_for_display), \
             patch("app.nppes.apply_coord_jitter"):
            response = self.client.get(
                "/api/search?lat=34.05&lng=-118.24&radius=10",
                headers={"X-Forwarded-For": "10.0.0.2"},
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["returned"], 1)
        self.assertEqual(len(payload["physicians"]), 1)
        self.assertEqual(payload["physicians"][0]["npi"], "2")
        self.assertEqual(payload["physicians"][0]["distance_miles"], 8.0)


if __name__ == "__main__":
    unittest.main()
