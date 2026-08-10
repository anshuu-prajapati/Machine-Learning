import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import download_video


class DownloadVideoTests(unittest.TestCase):
    def test_initialize_database_and_log_event(self):
        tmpdir = tempfile.mkdtemp(prefix="cliptest_", dir=str(Path(__file__).resolve().parent))
        db_path = Path(tmpdir) / "clips.db"

        try:
            conn = download_video.initialize_database(str(db_path))
            self.assertIsNotNone(conn)

            download_video.log_download_event(
                str(db_path),
                imei="123456",
                date_str="2026-08-08",
                start_time="01:01:01",
                end_time="01:02:00",
                status="success",
                file_path="/tmp/video.mp4",
                s3_url="https://example.com/video.mp4",
                error="",
            )

            conn.close()

            with sqlite3.connect(db_path) as db:
                row = db.execute(
                    "SELECT imei, status, s3_url FROM clip_downloads WHERE imei=?",
                    ("123456",),
                ).fetchone()

            self.assertEqual(row[0], "123456")
            self.assertEqual(row[1], "success")
            self.assertEqual(row[2], "https://example.com/video.mp4")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
