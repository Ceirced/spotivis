import os
from flask import render_template, request, current_app
from werkzeug.utils import secure_filename
import pyarrow.parquet as pq

from app import htmx
from app.main.first import bp


ALLOWED_EXTENSIONS = {'parquet'}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_parquet_file(file_path):
    try:
        pq.ParquetFile(file_path)
        return True
    except Exception:
        return False


@bp.route("/", methods=["GET"])
def index():
    title = "First"
    max_file_size_mb = MAX_FILE_SIZE // (1024 * 1024)
    if htmx.boosted:
        return render_template(
            "./first/partials/_content.html",
            title=title,
            max_file_size_mb=max_file_size_mb,
        )
    return render_template(
        "./first/index.html", title=title, max_file_size_mb=max_file_size_mb
    )


@bp.route("/upload", methods=["POST"])
def upload_file():
    if 'file' not in request.files:
        return (
            render_template(
                "./first/partials/_upload_error.html", error="No file part"
            ),
            400,
        )

    file = request.files['file']

    if file.filename == '':
        return (
            render_template(
                "./first/partials/_upload_error.html", error="No selected file"
            ),
            400,
        )

    if not allowed_file(file.filename):
        return (
            render_template(
                "./first/partials/_upload_error.html",
                error="Invalid file type. Only .parquet files are allowed",
            ),
            400,
        )

    # Check file size
    file.seek(0, os.SEEK_END)
    file_length = file.tell()
    file.seek(0)

    if file_length > MAX_FILE_SIZE:
        return (
            render_template(
                "./first/partials/_upload_error.html",
                error=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB",
            ),
            400,
        )

    # Create upload directory if it doesn't exist
    upload_folder = os.path.join(current_app.root_path, '..', 'uploads')
    os.makedirs(upload_folder, exist_ok=True)

    filename = secure_filename(file.filename)
    # Add timestamp to avoid collisions
    from datetime import datetime

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{timestamp}_{filename}"

    file_path = os.path.join(upload_folder, filename)

    try:
        file.save(file_path)

        # Validate that it's a valid parquet file
        if not validate_parquet_file(file_path):
            os.remove(file_path)
            return (
                render_template(
                    "./first/partials/_upload_error.html",
                    error="Invalid parquet file format",
                ),
                400,
            )

        return (
            render_template(
                "./first/partials/_upload_success.html",
                filename=filename,
                size=file_length,
                message="File uploaded successfully",
            ),
            200,
        )

    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        return (
            render_template(
                "./first/partials/_upload_error.html",
                error=f"Failed to save file: {str(e)}",
            ),
            500,
        )
