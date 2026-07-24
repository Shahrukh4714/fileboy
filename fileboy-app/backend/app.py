import os
import uuid
import subprocess
import shutil
import time
import logging
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from PIL import Image
import img2pdf
from pdf2image import convert_from_path
from pypdf import PdfReader, PdfWriter
import pikepdf

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = Flask(__name__)
CORS(app)

# Limit payload size to 50 MB
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

UPLOAD_DIR = "/tmp/fileboy/uploads"
OUTPUT_DIR = "/tmp/fileboy/outputs"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

IMAGE_FORMATS = {"jpeg", "jpg", "png", "webp", "gif", "bmp", "tiff"}
VIDEO_FORMATS = {"mp4", "mov", "webm", "avi", "mkv", "gif"}
AUDIO_FORMATS = {"mp3", "wav", "aac", "flac", "ogg", "m4a"}
DOC_FORMATS = {"pdf", "docx", "doc", "pptx", "ppt", "xlsx", "xls", "odt", "txt"}

def cleanup_old_files():
    """Remove output files older than 1 hour (3600s)."""
    now = time.time()
    try:
        for f in os.listdir(OUTPUT_DIR):
            fpath = os.path.join(OUTPUT_DIR, f)
            if os.path.isfile(fpath) and (now - os.path.getmtime(fpath) > 3600):
                os.remove(fpath)
            elif os.path.isdir(fpath) and (now - os.path.getmtime(fpath) > 3600):
                shutil.rmtree(fpath, ignore_errors=True)
    except Exception as e:
        logging.error(f"Cleanup error: {e}")

def get_ext(filename):
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

def detect_category(ext):
    if ext in IMAGE_FORMATS: return "image"
    if ext in VIDEO_FORMATS: return "video"
    if ext in AUDIO_FORMATS: return "audio"
    if ext in DOC_FORMATS: return "document"
    return "unknown"


@app.route("/api/detect", methods=["POST"])
def detect():
    """Given a filename, return category + available target formats."""
    data = request.get_json(silent=True) or {}
    filename = data.get("filename", "")
    ext = get_ext(filename)
    category = detect_category(ext)

    targets = {
        "image": ["jpeg", "png", "webp", "gif", "bmp", "pdf"],
        "video": ["mp4", "mov", "webm", "gif", "mp3"],
        "audio": ["mp3", "wav", "aac", "flac", "ogg"],
        "document": ["pdf", "docx", "pptx", "xlsx", "txt"],
        "unknown": []
    }

    return jsonify({
        "category": category,
        "source_ext": ext,
        "available_targets": [t for t in targets.get(category, []) if t != ext]
    })


@app.route("/api/convert", methods=["POST"])
def convert():
    cleanup_old_files()

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    target_format = request.form.get("target", "").lower()
    if not target_format:
        return jsonify({"error": "No target format specified"}), 400

    job_id = str(uuid.uuid4())[:8]
    original_name = file.filename or "file"
    source_ext = get_ext(original_name)
    base_name = original_name.rsplit(".", 1)[0] if "." in original_name else original_name

    input_path = os.path.join(UPLOAD_DIR, f"{job_id}_{original_name}")
    file.save(input_path)
    original_size = os.path.getsize(input_path)

    output_filename = f"{base_name}.{target_format}"
    output_path = os.path.join(OUTPUT_DIR, f"{job_id}_{output_filename}")

    category = detect_category(source_ext)
    logging.info(f"Processing job {job_id}: {original_name} -> {target_format} (category: {category})")

    try:
        if category == "image":
            convert_image(input_path, output_path, target_format)
        elif category == "video":
            convert_video(input_path, output_path, target_format)
        elif category == "audio":
            convert_audio(input_path, output_path, target_format)
        elif category == "document":
            convert_document(input_path, output_path, target_format, job_id)
        else:
            return jsonify({"error": f"Unsupported file type: {source_ext}"}), 400

        if not os.path.exists(output_path):
            return jsonify({"error": "Conversion produced no output"}), 500

        new_size = os.path.getsize(output_path)

        return jsonify({
            "success": True,
            "job_id": job_id,
            "output_filename": output_filename,
            "download_url": f"/api/download/{job_id}/{output_filename}",
            "original_size": original_size,
            "new_size": new_size,
        })

    except subprocess.CalledProcessError as e:
        logging.error(f"Command execution error in job {job_id}: {str(e)}")
        return jsonify({"error": f"Conversion process failed: {str(e)}"}), 500
    except Exception as e:
        logging.error(f"Unhandled error in job {job_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)


def convert_image(input_path, output_path, target_format):
    img = Image.open(input_path)

    if target_format == "pdf":
        rgb = img.convert("RGB")
        rgb.save(output_path, "PDF")
        return

    if target_format in ("jpeg", "jpg") and img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    save_format = "JPEG" if target_format in ("jpeg", "jpg") else target_format.upper()
    img.save(output_path, save_format)


def convert_video(input_path, output_path, target_format):
    if target_format == "mp3":
        cmd = ["ffmpeg", "-y", "-i", input_path, "-vn", "-acodec", "libmp3lame", output_path]
    elif target_format == "gif":
        cmd = ["ffmpeg", "-y", "-i", input_path, "-vf", "fps=10,scale=480:-1:flags=lanczos", output_path]
    else:
        cmd = ["ffmpeg", "-y", "-i", input_path, "-c:v", "libx264", "-c:a", "aac", output_path]
    subprocess.run(cmd, check=True, capture_output=True)


def convert_audio(input_path, output_path, target_format):
    cmd = ["ffmpeg", "-y", "-i", input_path, output_path]
    subprocess.run(cmd, check=True, capture_output=True)


def convert_document(input_path, output_path, target_format, job_id):
    outdir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(outdir, exist_ok=True)
    cmd = [
        "soffice", "--headless", "--convert-to", target_format,
        "--outdir", outdir, input_path
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=60)

    produced = [f for f in os.listdir(outdir) if f.endswith(f".{target_format}")]
    if produced:
        shutil.move(os.path.join(outdir, produced[0]), output_path)
    shutil.rmtree(outdir, ignore_errors=True)


@app.route("/api/download/<job_id>/<filename>")
def download(job_id, filename):
    # Security: sanitize filename to prevent path traversal
    safe_filename = os.path.basename(filename)
    safe_job_id = os.path.basename(job_id)
    target_path = os.path.join(OUTPUT_DIR, f"{safe_job_id}_{safe_filename}")

    # Verify target path is within OUTPUT_DIR
    real_target = os.path.realpath(target_path)
    real_outdir = os.path.realpath(OUTPUT_DIR)
    if not real_target.startswith(real_outdir):
        return jsonify({"error": "Invalid path"}), 403

    if not os.path.exists(real_target):
        return jsonify({"error": "File not found"}), 404

    return send_file(real_target, as_attachment=True, download_name=safe_filename)


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "fileboy-backend"
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
