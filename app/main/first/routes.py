from datetime import datetime
from pathlib import Path
from flask import render_template, request, current_app, make_response
from werkzeug.utils import secure_filename
import pyarrow.parquet as pq

from app import htmx, cache
from app.helpers.app_helpers import make_cache_key_with_htmx
from app.main.first import bp


ALLOWED_EXTENSIONS = {"parquet"}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_parquet_file(file_path):
    try:
        pq.ParquetFile(file_path)
        return True
    except Exception:
        return False


def add_cache_headers(response, max_age=300, private=True):
    """Add client-side cache headers to response."""
    if private:
        response.headers["Cache-Control"] = f"private, max-age={max_age}"
    else:
        response.headers["Cache-Control"] = f"public, max-age={max_age}"
    return response


@bp.route("/", methods=["GET"])
@cache.cached(timeout=60, make_cache_key=make_cache_key_with_htmx)
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


@bp.route("/preview/<filename>", methods=["GET"])
@cache.cached(
    timeout=300, make_cache_key=make_cache_key_with_htmx
)  # Cache for 5 minutes
def preview_file(filename):
    """Show file preview page with metadata and data preview."""
    upload_folder = Path(current_app.root_path).parent / "uploads"
    file_path = upload_folder / filename

    if not file_path.exists() or not file_path.suffix == ".parquet":
        return render_template("error.html", error="File not found"), 404

    file_stat = file_path.stat()

    # Extract original filename and timestamp
    parts = filename.split("_")
    if len(parts) >= 3:
        try:
            timestamp_str = f"{parts[0]}_{parts[1]}"
            upload_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            formatted_time = upload_time.strftime("%Y-%m-%d %H:%M:%S")
            original_name = "_".join(parts[2:])
        except (ValueError, IndexError):
            formatted_time = "Unknown"
            original_name = filename
    else:
        original_name = filename
        formatted_time = "Unknown"

    file_info = {
        "filename": filename,
        "original_name": original_name,
        "size_mb": round(file_stat.st_size / (1024 * 1024), 2),
        "upload_time": formatted_time,
    }

    if htmx.boosted:
        return render_template("./first/file_preview.html", file=file_info)
    return render_template("./first/file_preview.html", file=file_info)


@bp.route("/preview-data/<filename>", methods=["GET"])
@cache.cached(timeout=300)  # Cache for 5 minutes
def preview_data(filename):
    """Load and return the actual parquet file data preview."""
    upload_folder = Path(current_app.root_path).parent / "uploads"
    file_path = upload_folder / filename

    if not file_path.exists() or not file_path.suffix == ".parquet":
        return render_template("error.html", error="File not found"), 404

    try:
        # Read first 10 rows of the parquet file
        df = pq.read_table(str(file_path)).to_pandas()
        preview_df = df.head(10)

        # Convert to dict for template
        columns = preview_df.columns.tolist()
        rows = preview_df.values.tolist()

        response = make_response(
            render_template(
                "./first/partials/_preview_data.html",
                columns=columns,
                rows=rows,
                total_rows=len(df),
            )
        )
        return add_cache_headers(response, max_age=300)  # Cache for 5 minutes
    except Exception as e:
        return (
            render_template(
                "./first/partials/_preview_data.html",
                error=f"Error reading file: {str(e)}",
            ),
            500,
        )


@bp.route("/files", methods=["GET"])
def list_files():
    """List all uploaded files."""
    upload_folder = Path(current_app.root_path).parent / "uploads"
    files = []

    if upload_folder.exists():
        for file_path in upload_folder.glob("*.parquet"):
            filename = file_path.name
            file_stat = file_path.stat()

            # Extract original filename and timestamp
            # Expected format: YYYYMMDD_HHMMSS_original_filename.parquet
            parts = filename.split("_")
            if len(parts) >= 3:
                try:
                    # Reconstruct timestamp from first two parts
                    timestamp_str = f"{parts[0]}_{parts[1]}"
                    upload_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    formatted_time = upload_time.strftime("%Y-%m-%d %H:%M:%S")
                    # Original name is everything after the timestamp
                    original_name = "_".join(parts[2:])
                except (ValueError, IndexError):
                    formatted_time = "Unknown"
                    original_name = filename
            else:
                original_name = filename
                formatted_time = "Unknown"

            files.append(
                {
                    "filename": filename,
                    "original_name": original_name,
                    "size": file_stat.st_size,
                    "upload_time": formatted_time,
                    "size_mb": round(file_stat.st_size / (1024 * 1024), 2),
                }
            )

    # Sort by most recent first
    files.sort(key=lambda x: x["filename"], reverse=True)

    return render_template("./first/partials/_file_list.html", files=files)


@bp.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return (
            render_template(
                "./first/partials/_upload_error.html", error="No file part"
            ),
            400,
        )

    file = request.files["file"]

    if file.filename == "":
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
    file.seek(0, 2)  # Seek to end (SEEK_END = 2)
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
    upload_folder = Path(current_app.root_path).parent / "uploads"
    upload_folder.mkdir(exist_ok=True)

    filename = secure_filename(file.filename)
    # Add timestamp to avoid collisions
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{filename}"

    file_path = upload_folder / filename

    try:
        file.save(str(file_path))

        # Validate that it's a valid parquet file
        if not validate_parquet_file(str(file_path)):
            file_path.unlink()
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
        if file_path.exists():
            file_path.unlink()
        return (
            render_template(
                "./first/partials/_upload_error.html",
                error=f"Failed to save file: {str(e)}",
            ),
            500,
        )
