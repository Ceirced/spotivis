"""Routes for combining preprocessed datasets."""

import uuid
from pathlib import Path

from flask import current_app, jsonify, render_template, request, send_from_directory
from flask_htmx import make_response
from flask_login import current_user
from sqlalchemy import select

from app import db, htmx
from app.main.first import bp
from app.models import CombinedPreprocessingJob, PreprocessingJob, UploadedFile


@bp.route("/combine", methods=["GET"])
def combine_files():
    """Show the combine files interface."""
    # Get all completed preprocessing jobs for the current user
    stmt = (
        select(PreprocessingJob)
        .join(UploadedFile)
        .where(
            UploadedFile.user_id == current_user.id,
            PreprocessingJob.status == "completed",
        )
        .order_by(PreprocessingJob.completed_at.desc())
    )
    completed_jobs = db.session.scalars(stmt).all()

    return render_template("./first/combine_files.html", completed_jobs=completed_jobs)


@bp.route("/combine/start", methods=["POST"])
def start_combine_files():
    """Start the process of combining two preprocessed files."""
    first_job_id = request.form.get("first_job_id")
    second_job_id = request.form.get("second_job_id")

    if not first_job_id or not second_job_id:
        return (
            render_template(
                "./first/partials/_error.html",
                error="Please select both files to combine",
            ),
            422,
        )

    if first_job_id == second_job_id:
        return (
            render_template(
                "./first/partials/_error.html",
                error="Please select two different files",
            ),
            422,
        )

    # Verify both jobs exist and belong to the user
    first_job_stmt = (
        select(PreprocessingJob)
        .join(UploadedFile)
        .where(
            PreprocessingJob.uuid == first_job_id,
            UploadedFile.user_id == current_user.id,
            PreprocessingJob.status == "completed",
        )
    )
    first_job = db.session.scalar(first_job_stmt)

    second_job_stmt = (
        select(PreprocessingJob)
        .join(UploadedFile)
        .where(
            PreprocessingJob.uuid == second_job_id,
            UploadedFile.user_id == current_user.id,
            PreprocessingJob.status == "completed",
        )
    )
    second_job = db.session.scalar(second_job_stmt)

    if not first_job or not second_job:
        return (
            render_template(
                "./first/partials/_error.html", error="Invalid job selection"
            ),
            422,
        )

    # Create the combined job record
    combined_job = CombinedPreprocessingJob(
        first_job_id=first_job_id,
        second_job_id=second_job_id,
        user_id=current_user.id,
        status="processing",
    )
    db.session.add(combined_job)
    db.session.commit()

    # Start the celery task
    from app.tasks.combine_datasets import combine_preprocessed_datasets

    task = combine_preprocessed_datasets.delay(str(combined_job.uuid))

    # Update with task ID
    combined_job.task_id = task.id
    db.session.commit()

    return render_template(
        "./first/partials/_combine_started.html",
        task_id=task.id,
        combined_job_id=combined_job.uuid,
    )


@bp.route("/combine/status/<task_id>", methods=["GET"])
def combine_status(task_id):
    """Check the status of a combine task."""
    from app.tasks.combine_datasets import combine_preprocessed_datasets

    task = combine_preprocessed_datasets.AsyncResult(task_id)

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
    else:  # FAILURE
        response = {
            "state": task.state,
            "current": 0,
            "total": 100,
            "status": str(task.info),
            "percent": 0,
        }

    if htmx:
        return render_template(
            "./first/partials/_combine_progress.html",
            task_id=task_id,
            task_state=response["state"],
            percent=response["percent"],
            status=response["status"],
            result=response.get("result"),
        )
    else:
        return jsonify(response)


@bp.route("/combine/history", methods=["GET"])
def combined_history():
    """Display history of combined preprocessing jobs."""
    stmt = (
        select(CombinedPreprocessingJob)
        .where(CombinedPreprocessingJob.user_id == current_user.id)
        .order_by(CombinedPreprocessingJob.started_at.desc())
    )
    combined_jobs = db.session.scalars(stmt).all()

    return render_template(
        "./first/partials/_combined_history.html", combined_jobs=combined_jobs
    )


@bp.route("/combine/view/<uuid:job_id>", methods=["GET"])
def view_combined_graph(job_id: uuid.UUID):
    """View the combined graph visualization."""
    stmt = select(CombinedPreprocessingJob).where(
        CombinedPreprocessingJob.uuid == str(job_id),
        CombinedPreprocessingJob.user_id == current_user.id,
        CombinedPreprocessingJob.status == "completed",
    )
    combined_job = db.session.scalar(stmt)

    if not combined_job:
        return (render_template("errors/404.html", error="Combined job not found"), 404)

    return render_template("./first/combined_graph_preview.html", job=combined_job)


@bp.route("/combine/data/<uuid:job_id>/nodes", methods=["GET"])
def combined_graph_nodes_data(job_id: uuid.UUID):
    """Serve nodes data for combined graph visualization."""
    stmt = select(CombinedPreprocessingJob).where(
        CombinedPreprocessingJob.uuid == str(job_id),
        CombinedPreprocessingJob.user_id == current_user.id,
        CombinedPreprocessingJob.status == "completed",
    )
    job = db.session.scalar(stmt)

    if not job:
        return jsonify({"error": "Combined job not found"}), 404

    try:
        if not job.nodes_file:
            return jsonify({"error": "No nodes file available"}), 404

        # Get the nodes file path
        preprocessed_data_dir = current_app.config.get(
            "PREPROCESSED_DATA_DIR", "preprocessed"
        )
        nodes_path = (
            Path(current_app.static_folder) / preprocessed_data_dir / job.nodes_file  # type: ignore
        )

        if not nodes_path.exists():
            return jsonify({"error": f"Nodes file not found at {nodes_path}"}), 404

        return send_from_directory(
            str(nodes_path.parent), nodes_path.name, as_attachment=False
        )

    except Exception as e:
        return jsonify({"error": f"Error reading nodes data: {str(e)}"}), 500


@bp.route("/combine/data/<uuid:job_id>/edges", methods=["GET"])
def combined_graph_edges_data(job_id: uuid.UUID):
    """Serve edges data for combined graph visualization."""
    stmt = select(CombinedPreprocessingJob).where(
        CombinedPreprocessingJob.uuid == str(job_id),
        CombinedPreprocessingJob.user_id == current_user.id,
        CombinedPreprocessingJob.status == "completed",
    )
    job = db.session.scalar(stmt)

    if not job:
        return jsonify({"error": "Combined job not found"}), 404

    try:
        if not job.edges_file:
            return jsonify({"error": "No edges file available"}), 404

        # Get the edges file path
        preprocessed_data_dir = current_app.config.get(
            "PREPROCESSED_DATA_DIR", "preprocessed"
        )
        edges_path = (
            Path(current_app.static_folder) / preprocessed_data_dir / job.edges_file  # type: ignore
        )
        if not edges_path.exists():
            return jsonify({"error": f"Edges file not found at {edges_path}"}), 404
        return send_from_directory(
            str(edges_path.parent), edges_path.name, as_attachment=False
        )
    except Exception as e:
        return jsonify({"error": f"Error reading edges data: {str(e)}"}), 500


@bp.route("/combine/cancel/<task_id>", methods=["POST"])
def cancel_combine_job(task_id):
    """Cancel a running combine task."""
    from app.tasks.combine_datasets import combine_preprocessed_datasets

    task = combine_preprocessed_datasets.AsyncResult(task_id)
    # Check if task exists and is cancellable
    if task.state in ["PENDING", "PROGRESS"]:
        # Revoke the task
        task.revoke(terminate=True)
        # Update the database status
        stmt = select(CombinedPreprocessingJob).where(
            CombinedPreprocessingJob.task_id == task_id
        )
        job = db.session.scalar(stmt)
        if job:
            job.status = "cancelled"
            job.completed_at = db.func.current_timestamp()
            job.error_message = "Task cancelled by user"
            db.session.commit()
        # Return empty content to clear the progress display
        from flask_htmx import make_response

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


@bp.route("/combine/publish/<uuid:job_id>", methods=["POST"])
def publish_combined_graph(job_id: uuid.UUID):
    """Publish a combined preprocessing job graph to the public gallery."""
    from datetime import datetime

    from flask import flash
    from flask_login import current_user

    stmt = select(CombinedPreprocessingJob).where(
        CombinedPreprocessingJob.uuid == str(job_id),
        CombinedPreprocessingJob.user_id == current_user.id,
    )
    job = db.session.scalar(stmt)

    if not job or job.status != "completed":
        flash("Job not found or not completed", "error")
        return "", 404

    job.published = True
    job.published_at = datetime.now()
    db.session.commit()

    flash("Combined graph published successfully!", "success")
    return make_response(
        render_template(
            "first/partials/_publish_button.html",
            published=True,
            job_id=job.uuid,
            is_combined=True,
        ),
        200,
        {"HX-Trigger": "flash-update"},
    )


@bp.route("/combine/unpublish/<uuid:job_id>", methods=["POST"])
def unpublish_combined_graph(job_id: uuid.UUID):
    """Unpublish a combined preprocessing job graph from the public gallery."""
    from flask import flash
    from flask_login import current_user

    stmt = select(CombinedPreprocessingJob).where(
        CombinedPreprocessingJob.uuid == str(job_id),
        CombinedPreprocessingJob.user_id == current_user.id,
    )
    job = db.session.scalar(stmt)

    if not job:
        flash("Job not found", "error")
        return "", 404

    job.published = False
    job.published_at = None
    db.session.commit()

    flash("Combined graph unpublished successfully!", "success")
    return make_response(
        render_template(
            "first/partials/_publish_button.html",
            published=False,
            job_id=job.uuid,
            is_combined=True,
        ),
        200,
        {"HX-Trigger": "flash-update"},
    )
