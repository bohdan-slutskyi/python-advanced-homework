"""Verify the exported Postman collection stays in sync with its generator."""

import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase

ROOT = Path(__file__).resolve().parents[1]
POSTMAN = ROOT / "postman"


class PostmanGenerationTests(SimpleTestCase):
    def test_collection_and_environment_are_reproducible(self):
        with TemporaryDirectory(prefix="lms271-postman-") as folder:
            generated = Path(folder)
            script = generated / "build_collection.py"
            script.write_bytes((POSTMAN / "build_collection.py").read_bytes())
            subprocess.run(
                [sys.executable, str(script)],
                check=True,
                capture_output=True,
                text=True,
            )
            for name in (
                "Django.postman_collection.json",
                "Django.local.postman_environment.json",
            ):
                expected = json.loads((POSTMAN / name).read_text())
                actual = json.loads((generated / name).read_text())
                self.assertEqual(actual, expected, f"{name} differs from generator")

        collection = json.loads(
            (POSTMAN / "Django.postman_collection.json").read_text()
        )
        self.assertEqual(sum(len(group["item"]) for group in collection["item"]), 41)

        for folder in collection["item"]:
            if folder["name"] not in ("Demo flow", "Bookings"):
                continue
            requests = {item["name"]: item for item in folder["item"]}
            create_events = requests["Create booking — Tenant"]["event"]
            confirm_events = requests["Confirm booking — Landlord"]["event"]
            create_scripts = "\n".join(
                line
                for event in create_events
                if event["listen"] == "test"
                for line in event["script"]["exec"]
            )
            confirm_scripts = "\n".join(
                line for event in confirm_events for line in event["script"]["exec"]
            )
            self.assertIn("booking_total_price", create_scripts)
            self.assertIn("booking_total_price", confirm_scripts)
            self.assertIn("total_price", confirm_scripts)

        for name in (
            "Django.local.postman_environment.json",
            "Django.docker.postman_environment.json",
        ):
            environment = json.loads((POSTMAN / name).read_text())
            vars_by_key = {item["key"]: item for item in environment["values"]}
            self.assertIn("booking_total_price", vars_by_key)
            self.assertEqual(vars_by_key["booking_total_price"]["value"], "")
