import sys
import os
import subprocess
import imageio_ffmpeg
import yt_dlp

def main():
    if len(sys.argv) < 2:
        print("Usage: python cli.py <youtube_url> [output_dir]")
        sys.exit(1)
    url = sys.argv[1]
    outdir = sys.argv[2] if len(sys.argv) > 2 else "."
    os.makedirs(outdir, exist_ok=True)
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(outdir, "%(title)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        downloaded = ydl.prepare_filename(info)
        title = info.get("title", "audio")
    safe = "".join(c for c in title if c.isalnum() or c in " _-").strip() or "audio"
    mp3_path = os.path.join(outdir, safe + ".mp3")
    subprocess.run([ffmpeg, "-y", "-i", downloaded, "-vn", "-ar", "44100", "-ac", "2", "-b:a", "192k", mp3_path],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if os.path.exists(downloaded) and downloaded != mp3_path:
            os.remove(downloaded)
    except OSError:
        pass
    print("Saved:", mp3_path)

if __name__ == "__main__":
    main()