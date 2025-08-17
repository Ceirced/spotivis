import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
from flask import current_app, jsonify, render_template, request, send_from_directory
from flask_htmx import make_response  # type: ignore
from flask_login import current_user  # type: ignore
from loguru import logger
from sqlalchemy import select
from werkzeug.utils import secure_filename

from app import cache, db, htmx
from app.helpers.app_helpers import make_cache_key_with_htmx
from app.main.first import bp
from app.models import PlaylistEnrichmentJob, PreprocessingJob, UploadedFile
from app.tasks.playlist_enrichment import enrich_playlist_nodes
from app.tasks.preprocessing import preprocess_spotify_data_original

ALLOWED_EXTENSIONS = {"parquet"}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_parquet_file(file_path):
    try:
        parquet_file = pq.ParquetFile(file_path)
        schema = parquet_file.schema_arrow
        column_names = [field.name for field in schema]

        required_columns = {"isrc", "playlist_id", "thu_date"}
        missing_columns = required_columns - set(column_names)

        if missing_columns:
            return (
                False,
                f"Missing required columns: {', '.join(sorted(missing_columns))}",
            )

        return True, None
    except Exception as e:
        return False, f"Invalid parquet file: {str(e)}"


def add_cache_headers(response, max_age=300, private=True):
    """Add client-side cache headers to response."""
    if private:
        response.headers["Cache-Control"] = f"private, max-age={max_age}"
    else:
        response.headers["Cache-Control"] = f"public, max-age={max_age}"
    return response


@bp.route("/", methods=["GET"])
@cache.cached(
    timeout=60,
    make_cache_key=make_cache_key_with_htmx,
    unless=lambda: current_app.config.get("DEBUG", False),
)
def index():
    title = "First"
    max_file_size_mb = MAX_FILE_SIZE // (1024 * 1024)
    return render_template(
        "./first/index.html", title=title, max_file_size_mb=max_file_size_mb
    )


@bp.route("/preview/<filename>", methods=["GET"])
@cache.cached(
    timeout=300,
    make_cache_key=make_cache_key_with_htmx,
    unless=lambda: current_app.config.get("DEBUG", False),
)  # Cache for 5 minutes
def preview_file(filename):
    """Show file preview page with metadata and data preview."""
    upload_folder = Path(current_app.root_path).parent / "uploads"
    file_path = upload_folder / filename

    if not file_path.exists() or not file_path.suffix == ".parquet":
        return render_template("errors/404.html", error="File not found"), 404

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

    # Check for running preprocessing jobs for this file
    stmt = select(UploadedFile).where(UploadedFile.filename == filename)
    uploaded_file = db.session.scalar(stmt)

    running_job = None
    if uploaded_file:
        # Look for any running or pending jobs for this file (exclude cancelled)
        job_stmt = (
            select(PreprocessingJob)
            .where(PreprocessingJob.uploaded_file_id == uploaded_file.id)
            .where(PreprocessingJob.status.in_(["pending", "processing"]))
            .order_by(PreprocessingJob.started_at.desc())
        )
        running_job = db.session.scalar(job_stmt)

    completed_job = next(
        (job for job in uploaded_file.preprocessing_jobs if job.status == "completed"),
        None,
    )

    file_info = {
        "filename": filename,
        "original_name": original_name,
        "size_mb": round(file_stat.st_size / (1024 * 1024), 2),
        "upload_time": formatted_time,
    }

    return render_template(
        "./first/file_preview.html",
        file=file_info,
        running_job=running_job,
        completed_job=completed_job,
    )


@bp.route("/preview-data/<filename>", methods=["GET"])
@cache.cached(
    timeout=300,
    unless=lambda: current_app.config.get("DEBUG", False),
)  # Cache for 5 minutes
def preview_data(filename):
    """Load and return the actual parquet file data preview."""
    upload_folder = Path(current_app.root_path).parent / "uploads"
    file_path = upload_folder / filename

    if not file_path.exists() or not file_path.suffix == ".parquet":
        return render_template("errors/404.html", error="File not found"), 422

    try:
        # Read only first 10 rows of the parquet file for preview
        parquet_file = pq.ParquetFile(str(file_path))

        total_rows = parquet_file.metadata.num_rows

        # Read only first 10 rows
        first_batch = next(parquet_file.iter_batches(batch_size=10))
        preview_df = first_batch.to_pandas()

        # Convert to dict for template
        columns = preview_df.columns.tolist()
        rows = preview_df.values.tolist()

        response = make_response(
            render_template(
                "./first/partials/_preview_data.html",
                columns=columns,
                rows=rows,
                total_rows=total_rows,
            )
        )
        if not current_app.config.get("DEBUG", False):
            return add_cache_headers(response, max_age=300)  # Cache for 5 minutes
        else:
            return response
    except Exception as e:
        return (
            render_template(
                "./first/partials/_preview_data.html",
                error=f"Error reading file: {str(e)}",
            ),
            500,
        )


@bp.route("/view-processed/<uuid:job_id>/<file_type>", methods=["GET"])
@cache.cached(
    timeout=300,
    make_cache_key=make_cache_key_with_htmx,
    unless=lambda: current_app.config.get("DEBUG", False),
)  # Cache for 5 minutes
def view_processed_file(job_id: uuid.UUID, file_type: str):
    """View processed edges or nodes CSV file from a completed job."""
    if file_type not in ["edges", "nodes"]:
        return render_template("errors/404.html", error="Invalid file type"), 404

    stmt = (
        select(PreprocessingJob)
        .join(UploadedFile)
        .where(
            PreprocessingJob.uuid == str(job_id),
            UploadedFile.user_id == current_user.id,
        )
    )
    job = db.session.scalar(stmt)

    if not job or job.status != "completed":
        return (
            render_template("errors/404.html", error="Job not found or not completed"),
            404,
        )

    try:
        # Get the appropriate file path
        if file_type == "edges":
            if not job.edges_file:
                return (
                    render_template("errors/404.html", error="No edges file available"),
                    404,
                )
            file_name = job.edges_file
        else:  # nodes
            if not job.nodes_file:
                return (
                    render_template("errors/404.html", error="No nodes file available"),
                    404,
                )
            file_name = job.nodes_file

        # Resolve path relative to static directory
        preprocessed_data_dir = current_app.config.get(
            "PREPROCESSED_DATA_DIR", "preprocessed"
        )
        file_path = Path(current_app.static_folder) / preprocessed_data_dir / file_name  # type: ignore

        if not file_path.exists():
            return (
                render_template(
                    "errors/404.html", error=f"File not found: {file_name}"
                ),
                404,
            )

        # Read CSV file with pagination
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 100, type=int)
        per_page = min(per_page, 1000)  # Cap at 1000 rows per page

        # Read the CSV file
        df = pd.read_csv(file_path)
        total_rows = len(df)

        # Calculate pagination
        offset = (page - 1) * per_page
        df_page = df.iloc[offset : offset + per_page]

        # Convert to dict for template
        columns = df_page.columns.tolist()
        rows = df_page.values.tolist()

        # Calculate pagination info
        total_pages = (total_rows + per_page - 1) // per_page

        enrichment_stmt = select(PlaylistEnrichmentJob).where(
            PlaylistEnrichmentJob.preprocessing_job_id == str(job_id),
        )

        enrichment_jobs = db.session.scalars(enrichment_stmt).all()
        enriched = any(job.status == "completed" for job in enrichment_jobs)

        # might be a problem if there are multiple
        job_in_progress = next(
            (job for job in enrichment_jobs if job.status == "processing"), None
        )

        return render_template(
            "./first/processed_view.html",
            job_id=job_id,
            file_type=file_type,
            file_name=file_name,
            columns=columns,
            rows=rows,
            total_rows=total_rows,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            uploaded_file=job.uploaded_file,
            enrichment_job=job_in_progress if job_in_progress else None,
            enriched=enriched,
        )
    except Exception as e:
        logger.error(f"Error reading processed file: {e}")
        return (
            render_template("errors/500.html", error=f"Error reading file: {str(e)}"),
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
            render_template("./first/partials/_error.html", error="No file part"),
            422,
        )

    file = request.files["file"]

    if file.filename == "":
        return (
            render_template("./first/partials/_error.html", error="No selected file"),
            422,
        )

    if not allowed_file(file.filename):
        return (
            render_template(
                "./first/partials/_error.html",
                error="Invalid file type. Only .parquet files are allowed",
            ),
            422,
        )

    # Check file size
    file.seek(0, 2)  # Seek to end (SEEK_END = 2)
    file_length = file.tell()
    file.seek(0)

    if file_length > MAX_FILE_SIZE:
        return (
            render_template(
                "./first/partials/_error.html",
                error=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB",
            ),
            422,
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
        is_valid, error_message = validate_parquet_file(str(file_path))
        if not is_valid:
            file_path.unlink()
            return (
                render_template(
                    "./first/partials/_error.html",
                    error=error_message,
                ),
                422,
            )

        # Save file metadata to database
        uploaded_file = UploadedFile(
            filename=filename,
            original_filename=file.filename,
            file_size=file_length,
            user_id=current_user.id if current_user.is_authenticated else None,
        )
        db.session.add(uploaded_file)
        db.session.commit()

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
                "./first/partials/_error.html",
                error=f"Failed to save file: {str(e)}",
            ),
            422,
        )


@bp.route("/preprocess/<filename>", methods=["POST"])
def start_preprocessing(filename):
    """Start preprocessing task for uploaded parquet file."""
    upload_folder = Path(current_app.root_path).parent / "uploads"
    file_path = upload_folder / filename

    if not file_path.exists() or not file_path.suffix == ".parquet":
        return (
            render_template("./first/partials/_error.html", error="File not found"),
            422,
        )

    # Get the uploaded file record using SQLAlchemy 2.0 style
    stmt = select(UploadedFile).where(UploadedFile.filename == filename)
    uploaded_file = db.session.scalar(stmt)

    if not uploaded_file:
        return (
            render_template(
                "./first/partials/_error.html",
                error="File record not found in database",
            ),
            422,
        )

    # Check if there's already a running job for this file (exclude cancelled)
    job_stmt = (
        select(PreprocessingJob)
        .where(PreprocessingJob.uploaded_file_id == uploaded_file.id)
        .where(PreprocessingJob.status.in_(["pending", "processing"]))
        .order_by(PreprocessingJob.started_at.desc())
    )
    existing_job = db.session.scalar(job_stmt)

    if existing_job:
        return (
            render_template(
                "./first/partials/_error.html",
                error="A preprocessing job is already running for this file",
            ),
            422,
        )

    # Start the Celery task - it will create the job record internally
    task = preprocess_spotify_data_original.delay(filename)

    return render_template(
        "./first/partials/_preprocess_started.html", task_id=task.id, filename=filename
    )


@bp.route("/task-status/<task_id>", methods=["GET"])
def task_status(task_id):
    """Check the status of a preprocessing task."""
    task = preprocess_spotify_data_original.AsyncResult(task_id)

    if task.state == "PENDING":
        response = {
            "state": task.state,
            "current": 0,
            "total": 100,
            "status": "Task pending...",
            "percent": 0,
        }
    elif task.state == "PROGRESS":
        response = {
            "state": task.state,
            "current": task.info.get("current", 0),
            "total": task.info.get("total", 100),
            "status": task.info.get("status", ""),
            "percent": task.info.get("percent", 0),
        }
    elif task.state == "SUCCESS":
        response = {
            "state": task.state,
            "current": 100,
            "total": 100,
            "status": "Complete!",
            "percent": 100,
            "result": task.info.get("result", task.result),
        }
    elif task.state == "REVOKED":
        response = {
            "state": "CANCELLED",
            "current": 0,
            "total": 100,
            "status": "Task cancelled",
            "percent": 0,
        }
    else:  # FAILURE
        response = {
            "state": task.state,
            "current": 0,
            "total": 100,
            "status": str(task.info),
            "percent": 0,
        }

    if htmx:
        # Return HTML partial for HTMX
        template = render_template(
            "./first/partials/_task_progress.html",
            task_id=task_id,
            task_state=response["state"],
            percent=response["percent"],
            status=response["status"],
            result=response.get("result"),
        )

        return make_response(
            template, refresh=True if response["state"] == "SUCCESS" else False
        )  # Trigger HTMX refresh only on success
    else:
        # Return JSON for other requests
        return jsonify(response)


@bp.route("/cancel-job/<task_id>", methods=["POST"])
def cancel_job(task_id):
    """Cancel a running preprocessing task."""
    task = preprocess_spotify_data_original.AsyncResult(task_id)

    # Check if task exists and is cancellable
    if task.state in ["PENDING", "PROGRESS"]:
        # Revoke the task
        task.revoke(terminate=True)

        # Update the database status
        stmt = select(PreprocessingJob).where(PreprocessingJob.task_id == task_id)
        job = db.session.scalar(stmt)

        if job:
            job.status = "cancelled"
            job.completed_at = db.func.current_timestamp()
            job.error_message = "Task cancelled by user"
            db.session.commit()

        # Return empty content to clear the progress display
        response = make_response("", trigger="refresh")  # Trigger HTMX refresh
        return response
    else:
        return (
            render_template(
                "./first/partials/_error.html",
                error="Task cannot be cancelled (not running or already completed)",
            ),
            422,
        )


@bp.route("/preprocessing-history", methods=["GET"])
@bp.route("/preprocessing-history/<filename>", methods=["GET"])
def preprocessing_history(filename=None):
    """Display preprocessing history for uploaded files."""
    # Base query for user's jobs
    stmt = (
        select(PreprocessingJob)
        .join(UploadedFile)
        .where(UploadedFile.user_id == current_user.id)
    )

    # If filename is provided, filter by that specific file
    if filename:
        stmt = stmt.where(UploadedFile.filename == filename)

    stmt = stmt.order_by(PreprocessingJob.started_at.desc())
    jobs = db.session.scalars(stmt).all()

    # Set hide_file_column flag when showing jobs for a specific file
    hide_file_column = filename is not None

    return render_template(
        "./first/partials/_preprocessing_history.html",
        jobs=jobs,
        hide_file_column=hide_file_column,
    )


@bp.route("/graph-preview/<uuid:job_id>", methods=["GET"])
def graph_preview(job_id: uuid.UUID):
    """Preview processed graph data."""
    logger.debug(f"Fetching graph preview for job_id: {job_id}")
    stmt = (
        select(PreprocessingJob)
        .join(UploadedFile)
        .where(
            PreprocessingJob.uuid == str(job_id),
            UploadedFile.user_id == current_user.id,
        )
    )
    job = db.session.scalar(stmt)
    if not job or job.status != "completed":
        return (
            render_template(
                "error.html", error="Preprocessing job not found or not completed"
            ),
            422,
        )

    return render_template(
        "./first/graph_preview.html",
        job=job,
    )


@bp.route("/graph-data/<uuid:job_id>/nodes", methods=["GET"])
def graph_nodes_data(job_id: uuid.UUID):
    """Serve nodes data for graph visualization."""
    stmt = (
        select(PreprocessingJob)
        .join(UploadedFile)
        .where(
            PreprocessingJob.uuid == str(job_id),
            UploadedFile.user_id == current_user.id,
        )
    )
    job = db.session.scalar(stmt)

    if not job or job.status != "completed":
        return jsonify({"error": "Job not found or not completed"}), 404

    try:
        if not job.nodes_file:
            return jsonify({"error": "No nodes file path set"}), 404

        # Resolve path relative to static directory
        preprocessed_data_dir = current_app.config.get(
            "PREPROCESSED_DATA_DIR", "preprocessed"
        )
        nodes_path = (
            Path(current_app.static_folder) / preprocessed_data_dir / job.nodes_file  # type: ignore
        )
        logger.debug(
            f"nodes_file: {job.nodes_file}, resolved_path: {nodes_path}, exists: {nodes_path.exists()}"
        )

        if not nodes_path.exists():
            return jsonify({"error": f"Nodes file not found at {nodes_path}"}), 404

        return send_from_directory(
            str(nodes_path.parent), nodes_path.name, as_attachment=False
        )

    except Exception as e:
        logger.error(f"Error reading nodes file: {e}")
        return jsonify({"error": "Error reading nodes data"}), 500


@bp.route("/graph-data/<uuid:job_id>/edges", methods=["GET"])
def graph_edges_data(job_id: uuid.UUID):
    """Serve edges data for graph visualization."""
    stmt = (
        select(PreprocessingJob)
        .join(UploadedFile)
        .where(
            PreprocessingJob.uuid == str(job_id),
            UploadedFile.user_id == current_user.id,
        )
    )
    job = db.session.scalar(stmt)

    if not job or job.status != "completed":
        return jsonify({"error": "Job not found or not completed"}), 404

    try:
        if not job.edges_file:
            return jsonify({"error": "No edges file path set"}), 404

        # Resolve path relative to static directory
        preprocessed_data_dir = current_app.config.get(
            "PREPROCESSED_DATA_DIR", "preprocessed"
        )
        edges_path = (
            Path(current_app.static_folder) / preprocessed_data_dir / job.edges_file  # type: ignore
        )
        logger.debug(
            f"edges_file: {job.edges_file}, resolved_path: {edges_path}, exists: {edges_path.exists()}"
        )

        logger.debug(
            f"static_folder: {current_app.static_folder}, edges_file: {job.edges_file}"
        )
        if not edges_path.exists():
            return jsonify({"error": f"Edges file not found at {edges_path}"}), 404

        return send_from_directory(
            str(edges_path.parent),
            edges_path.name,
            as_attachment=False,
        )
    except Exception as e:
        logger.error(f"Error reading edges file: {e}")
        return jsonify({"error": "Error reading edges data"}), 500


@bp.route("/enrich-playlists/<uuid:job_id>", methods=["POST"])
def start_playlist_enrichment(job_id: uuid.UUID):
    """Start playlist enrichment task for processed nodes."""
    stmt = (
        select(PreprocessingJob)
        .join(UploadedFile)
        .where(
            PreprocessingJob.uuid == str(job_id),
            UploadedFile.user_id == current_user.id,
        )
    )
    preprocessing_job = db.session.scalar(stmt)

    if not preprocessing_job or preprocessing_job.status != "completed":
        return (
            render_template(
                "./first/partials/_error.html",
                error="Preprocessing job not found or not completed",
            ),
            422,
        )

    if not preprocessing_job.nodes_file:
        return (
            render_template(
                "./first/partials/_error.html",
                error="No nodes file available for enrichment",
            ),
            422,
        )

    # Check if there's already a running enrichment job for this preprocessing job
    job_stmt = (
        select(PlaylistEnrichmentJob)
        .where(PlaylistEnrichmentJob.preprocessing_job_id == str(job_id))
        .where(PlaylistEnrichmentJob.status.in_(["pending", "processing"]))
    )
    existing_job = db.session.scalar(job_stmt)

    if existing_job:
        return (
            render_template(
                "./first/partials/_error.html",
                error="An enrichment job is already running for this preprocessing job",
            ),
            422,
        )

    # Start the Celery task - it will create the job record internally
    task = enrich_playlist_nodes.delay(str(job_id))

    return render_template(
        "./first/partials/_enrichment_started.html",
        task_id=task.id,
        job_uuid=None,  # We don't have the UUID yet as it's created in the task
    )


@bp.route("/enrichment-status/<task_id>", methods=["GET"])
def enrichment_status(task_id):
    """Check the status of an enrichment task."""
    task = enrich_playlist_nodes.AsyncResult(task_id)

    if task.state == "PENDING":
        response = {
            "state": task.state,
            "current": 0,
            "total": 100,
            "status": "Task pending...",
            "percent": 0,
            "found": 0,
            "not_found": 0,
        }
    elif task.state == "PROGRESS":
        response = {
            "state": task.state,
            "current": task.info.get("current", 0),
            "total": task.info.get("total", 100),
            "status": task.info.get("status", ""),
            "percent": task.info.get("percent", 0),
            "found": task.info.get("found", 0),
            "not_found": task.info.get("not_found", 0),
        }
    elif task.state == "SUCCESS":
        response = {
            "state": task.state,
            "current": 100,
            "total": 100,
            "status": "Complete!",
            "percent": 100,
            "found": task.info.get("found", 0),
            "not_found": task.info.get("not_found", 0),
            "result": task.info.get("result", task.result),
        }
    elif task.state == "REVOKED":
        response = {
            "state": "CANCELLED",
            "current": 0,
            "total": 100,
            "status": "Task cancelled",
            "percent": 0,
            "found": 0,
            "not_found": 0,
        }
    else:  # FAILURE
        response = {
            "state": task.state,
            "current": 0,
            "total": 100,
            "status": str(task.info),
            "percent": 0,
            "found": 0,
            "not_found": 0,
        }

    if htmx:
        # Return HTML partial for HTMX
        return render_template(
            "./first/partials/_enrichment_progress.html",
            task_id=task_id,
            task_state=response["state"],
            percent=response["percent"],
            status=response["status"],
            found=response["found"],
            not_found=response["not_found"],
            result=response.get("result"),
        )
    else:
        # Return JSON for other requests
        return jsonify(response)


@bp.route("/cancel-enrichment/<task_id>", methods=["POST"])
def cancel_enrichment_job(task_id):
    """Cancel a running enrichment task."""
    task = enrich_playlist_nodes.AsyncResult(task_id)

    # Check if task exists and is cancellable
    if task.state in ["PENDING", "PROGRESS"]:
        # Revoke the task
        task.revoke(terminate=True)

        # Update the database status
        stmt = select(PlaylistEnrichmentJob).where(
            PlaylistEnrichmentJob.task_id == task_id
        )
        job = db.session.scalar(stmt)

        if job:
            job.status = "cancelled"
            job.completed_at = db.func.current_timestamp()
            job.error_message = "Task cancelled by user"
            db.session.commit()

        # Return empty content to clear the progress display
        response = make_response(
            "",
            trigger="refresh",  # Trigger HTMX refresh
        )
        return response
    else:
        return (
            render_template(
                "./first/partials/_error.html",
                error="Task cannot be cancelled (not running or already completed)",
            ),
            422,
        )
