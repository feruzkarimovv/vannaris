"""Operational artifacts must prove health without exposing private evidence."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest

from scripts.encrypt_recovery import encrypt
from scripts.run_status import publication_health, summarize


class TestPublicationHealth(unittest.TestCase):
    def test_current_manual_publication_does_not_prove_scheduler_delivery(self):
        result = publication_health({"week": "2026-W40", "trigger": "manual"}, dt.datetime(2026, 10, 4, tzinfo=dt.timezone.utc))
        self.assertFalse(result["healthy"])
        self.assertEqual(result["state"], "manual_only")

    def test_scheduled_current_publication_is_healthy(self):
        self.assertTrue(publication_health({"week": "2026-W40", "trigger": "scheduled"}, dt.datetime(2026, 10, 4, tzinfo=dt.timezone.utc))["healthy"])

    def test_week_53_year_boundary_counts_actual_calendar_weeks(self):
        result = publication_health({"week": "2020-W53", "trigger": "scheduled"}, dt.datetime(2021, 1, 4, tzinfo=dt.timezone.utc))
        self.assertEqual(result["weeks_behind"], 1)
        self.assertFalse(result["healthy"])

    def test_invalid_or_absent_publication_is_not_healthy(self):
        for week in (None, "not-a-week", "2026-W99"):
            with self.subTest(week=week):
                result = publication_health({"week": week}, dt.datetime(2026, 10, 4, tzinfo=dt.timezone.utc))
                self.assertFalse(result["healthy"])
                self.assertIsNone(result["weeks_behind"])


class TestSanitizedStatus(unittest.TestCase):
    def test_missing_database_is_never_created_by_status_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = summarize(root / "missing.db", root / "site")
            self.assertEqual(result["state"], "not_started")
            self.assertFalse((root / "missing.db").exists())

    def test_status_excludes_question_payload_and_error_text(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "private.db"
            with sqlite3.connect(db) as conn:
                conn.executescript("""
                    CREATE TABLE runs(id,week,started_at,finished_at,trigger,query_set_hash);
                    CREATE TABLE raw_responses(id,run_id,error,raw_payload);
                    CREATE TABLE judge_scores(response_id,judge_family);
                    INSERT INTO runs VALUES('run1','2026-W40','2026-10-01',NULL,'manual','digest');
                    INSERT INTO raw_responses VALUES('r1','run1','PRIVATE ERROR EXCERPT','PRIVATE WITHHELD QUESTION');
                    INSERT INTO judge_scores VALUES('r1','anthropic'),('r1','openai'),('r1','google');
                """)
            result = summarize(db, root / "site")
            serialized = json.dumps(result)
            self.assertNotIn("PRIVATE", serialized)
            self.assertEqual(result["state"], "interrupted")
            self.assertEqual(result["run"]["vendor_errors"], 1)
            self.assertEqual(result["run"]["complete_ensembles"], 0)

    def test_finished_incomplete_run_does_not_become_completed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db = root / "evidence.db"
            with sqlite3.connect(db) as conn:
                conn.executescript("""
                    CREATE TABLE runs(id,week,started_at,finished_at,trigger,query_set_hash,status);
                    CREATE TABLE raw_responses(id,run_id,error);
                    CREATE TABLE judge_scores(response_id,judge_family);
                    INSERT INTO runs VALUES('r','2026-W40','2026-10-01','2026-10-02','scheduled','digest','incomplete');
                """)
            self.assertEqual(summarize(db, root / "site")["state"], "incomplete")

    def test_failed_push_keeps_generated_export_separate_from_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            (root / "data" / "latest.json").write_text(json.dumps({"week": "2026-W40", "trigger": "scheduled"}))
            result = summarize(root / "missing.db", root, dt.datetime(2026, 10, 4, tzinfo=dt.timezone.utc), "failure")
            self.assertTrue(result["generated_export"]["healthy"])
            self.assertFalse(result["publication"]["healthy"])
            self.assertEqual(result["publication"]["state"], "not_published")


class TestEncryptedRecovery(unittest.TestCase):
    def test_public_recipient_envelope_restores_exact_private_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db, cert, key, envelope = [root / name for name in ("evidence.db", "recipient.pem", "private.pem", "evidence.p7m")]
            original = b"SYNTHETIC private recovery content\x00\x01"
            db.write_bytes(original)
            subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-noenc", "-subj", "/CN=Local recovery test", "-keyout", str(key), "-out", str(cert), "-days", "1"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            encrypt(db, cert, envelope)
            self.assertNotIn(original, envelope.read_bytes())
            restored = subprocess.run(["openssl", "cms", "-decrypt", "-binary", "-inform", "DER", "-in", str(envelope), "-recip", str(cert), "-inkey", str(key)], check=True, capture_output=True).stdout
            self.assertEqual(restored, original)
            self.assertEqual(db.read_bytes(), original)

    def test_private_key_is_rejected_and_original_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            db, cert = root / "evidence.db", root / "private.pem"
            db.write_bytes(b"evidence")
            cert.write_text("-----BEGIN PRIVATE KEY-----\nfixture\n")
            with self.assertRaisesRegex(ValueError, "public X.509"):
                encrypt(db, cert, root / "evidence.p7m")
            self.assertEqual(db.read_bytes(), b"evidence")


if __name__ == "__main__":
    unittest.main()
