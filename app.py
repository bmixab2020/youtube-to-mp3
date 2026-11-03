import os
import re
import uuid
import subprocess
import threading
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_file, url_for
import yt_dlp
import imageio_ffmpeg

app = Flask(__name__)
BASE_DIR = Path(__file__).resolve().parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
DOWNLOAD_DIR.mkdir(exist_ok=True)
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

JOBS = {}


def is_youtube_url(url: str) -> bool:
    return bool(re.search(r"(youtube\.com|youtu\.be)", url or "", re.IGNORECASE))


def run_job(job_id: str, url: str):
    job = JOBS[job_id]
    try:
        job["status"] = "downloading"
        outtmpl = str(DOWNLOAD_DIR / f"{job_id}.%(ext)s")
        opts = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "audio")
            downloaded = ydl.prepare_filename(info)
        mp3_path = DOWNLOAD_DIR / f"{job_id}.mp3"
        subprocess.run(
            [FFMPEG, "-y", "-i", downloaded, "-vn", "-ar", "44100", "-ac", "2", "-b:a", "192k", str(mp3_path)],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            if os.path.exists(downloaded) and downloaded != str(mp3_path):
                os.remove(downloaded)
        except OSError:
            pass
        job["title"] = title
        job["file"] = mp3_path.name
        job["status"] = "done"
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/convert", methods=["POST"])
def convert():
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or request.form.get("url") or "").strip()
    if not url or not is_youtube_url(url):
        return jsonify({"error": "Please provide a valid YouTube URL."}), 400
    job_id = uuid.uuid4().hex
    JOBS[job_id] = {"status": "queued", "url": url}
    threading.Thread(target=run_job, args=(job_id, url), daemon=True).start()
    return jsonify({"job_id": job_id})


@app.route("/status/<job_id>")
def status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Unknown job."}), 404
    resp = {"status": job["status"]}
    if job["status"] == "done":
        resp["title"] = job.get("title")
        resp["download_url"] = url_for("download", job_id=job_id)
    if job["status"] == "error":
        resp["error"] = job.get("error")
    return jsonify(resp)


@app.route("/download/<job_id>")
def download(job_id):
    job = JOBS.get(job_id)
    if not job or job.get("status") != "done":
        return jsonify({"error": "File not ready."}), 404
    path = DOWNLOAD_DIR / job["file"]
    if not path.exists():
        return jsonify({"error": "File missing."}), 404
    return send_file(path, as_attachment=True, download_name=f"{job.get('title','audio')}.mp3")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
