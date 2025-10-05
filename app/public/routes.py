from flask import redirect, render_template, url_for
from flask_security import current_user
from sqlalchemy import select

from app import db
from app.models import CombinedPreprocessingJob, PreprocessingJob, UploadedFile, User
from app.public import bp


@bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    # Fetch published graphs (both regular and combined)
    regular_graphs_stmt = (
        select(PreprocessingJob)
        .join(UploadedFile, PreprocessingJob.file_uuid == UploadedFile.uuid)
        .join(User, UploadedFile.user_id == User.id, isouter=True)
        .where(PreprocessingJob.published)
        .order_by(PreprocessingJob.published_at.desc())
        .limit(12)
    )

    combined_graphs_stmt = (
        select(CombinedPreprocessingJob)
        .join(User)
        .where(CombinedPreprocessingJob.published)
        .order_by(CombinedPreprocessingJob.published_at.desc())
        .limit(12)
    )

    regular_graphs = db.session.scalars(regular_graphs_stmt).all()
    combined_graphs = db.session.scalars(combined_graphs_stmt).all()

    # Combine and sort all graphs by published_at
    all_graphs = [
        {
            "type": "regular",
            "uuid": graph.uuid,
            "username": graph.uploaded_file.user.username
            if graph.uploaded_file.user
            else "Anonymous",
            "published_at": graph.published_at,
            "nodes": graph.final_nodes,
            "edges": graph.final_edges,
            "title": graph.uploaded_file.name,
        }
        for graph in regular_graphs
    ] + [
        {
            "type": "combined",
            "uuid": graph.uuid,
            "username": graph.user.username if graph.user else "Anonymous",
            "published_at": graph.published_at,
            "nodes": graph.total_nodes,
            "edges": graph.total_edges,
            "title": "Combined Graph",
        }
        for graph in combined_graphs
    ]

    # Sort by published_at (most recent first)
    all_graphs.sort(key=lambda x: x["published_at"] or "", reverse=True)

    return render_template("public/index.html", title="Home", graphs=all_graphs[:12])


@bp.route("/graph/<graph_type>/<uuid:graph_id>")
def view_graph(graph_type, graph_id):
    """View a published graph."""

    if graph_type == "regular":
        stmt = select(PreprocessingJob).where(
            PreprocessingJob.uuid == str(graph_id), PreprocessingJob.published
        )
        job = db.session.scalar(stmt)

        if not job:
            return render_template("errors/404.html", error="Graph not found"), 404

        return render_template(
            "public/graph_view.html",
            title=f"Graph by {job.uploaded_file.user.username if job.uploaded_file.user else 'Anonymous'}",
            job=job,
            graph_type="regular",
        )

    elif graph_type == "combined":
        stmt = select(CombinedPreprocessingJob).where(
            CombinedPreprocessingJob.uuid == str(graph_id),
            CombinedPreprocessingJob.published,
        )
        job = db.session.scalar(stmt)

        if not job:
            return render_template("errors/404.html", error="Graph not found"), 404

        return render_template(
            "public/graph_view.html",
            title=f"Combined Graph by {job.user.username if job.user else 'Anonymous'}",
            job=job,
            graph_type="combined",
        )

    return render_template("errors/404.html", error="Invalid graph type"), 404


@bp.route("/graph-data/<graph_type>/<uuid:graph_id>/nodes")
def graph_nodes_data(graph_type, graph_id):
    """Serve nodes data for a published graph."""
    from pathlib import Path

    from flask import current_app, jsonify, send_from_directory

    if graph_type == "regular":
        stmt = select(PreprocessingJob).where(
            PreprocessingJob.uuid == str(graph_id), PreprocessingJob.published
        )
        job = db.session.scalar(stmt)

        if not job or job.status != "completed":
            return jsonify({"error": "Job not found or not completed"}), 404

        if not job.nodes_file:
            return jsonify({"error": "No nodes file path set"}), 404

        preprocessed_data_dir = current_app.config.get(
            "PREPROCESSED_DATA_DIR", "preprocessed"
        )
        nodes_path = (
            Path(current_app.static_folder) / preprocessed_data_dir / job.nodes_file
        )

        if not nodes_path.exists():
            return jsonify({"error": f"Nodes file not found at {nodes_path}"}), 404

        return send_from_directory(
            str(nodes_path.parent), nodes_path.name, as_attachment=False
        )

    elif graph_type == "combined":
        stmt = select(CombinedPreprocessingJob).where(
            CombinedPreprocessingJob.uuid == str(graph_id),
            CombinedPreprocessingJob.published,
        )
        job = db.session.scalar(stmt)

        if not job or job.status != "completed":
            return jsonify({"error": "Job not found or not completed"}), 404

        if not job.nodes_file:
            return jsonify({"error": "No nodes file path set"}), 404

        preprocessed_data_dir = current_app.config.get(
            "PREPROCESSED_DATA_DIR", "preprocessed"
        )
        nodes_path = (
            Path(current_app.static_folder) / preprocessed_data_dir / job.nodes_file
        )

        if not nodes_path.exists():
            return jsonify({"error": f"Nodes file not found at {nodes_path}"}), 404

        return send_from_directory(
            str(nodes_path.parent), nodes_path.name, as_attachment=False
        )

    return jsonify({"error": "Invalid graph type"}), 404


@bp.route("/graph-data/<graph_type>/<uuid:graph_id>/edges")
def graph_edges_data(graph_type, graph_id):
    """Serve edges data for a published graph."""
    from pathlib import Path

    from flask import current_app, jsonify, send_from_directory

    if graph_type == "regular":
        stmt = select(PreprocessingJob).where(
            PreprocessingJob.uuid == str(graph_id), PreprocessingJob.published
        )
        job = db.session.scalar(stmt)

        if not job or job.status != "completed":
            return jsonify({"error": "Job not found or not completed"}), 404

        if not job.edges_file:
            return jsonify({"error": "No edges file path set"}), 404

        preprocessed_data_dir = current_app.config.get(
            "PREPROCESSED_DATA_DIR", "preprocessed"
        )
        edges_path = (
            Path(current_app.static_folder) / preprocessed_data_dir / job.edges_file
        )

        if not edges_path.exists():
            return jsonify({"error": f"Edges file not found at {edges_path}"}), 404

        return send_from_directory(
            str(edges_path.parent), edges_path.name, as_attachment=False
        )

    elif graph_type == "combined":
        stmt = select(CombinedPreprocessingJob).where(
            CombinedPreprocessingJob.uuid == str(graph_id),
            CombinedPreprocessingJob.published,
        )
        job = db.session.scalar(stmt)

        if not job or job.status != "completed":
            return jsonify({"error": "Job not found or not completed"}), 404

        if not job.edges_file:
            return jsonify({"error": "No edges file path set"}), 404

        preprocessed_data_dir = current_app.config.get(
            "PREPROCESSED_DATA_DIR", "preprocessed"
        )
        edges_path = (
            Path(current_app.static_folder) / preprocessed_data_dir / job.edges_file
        )

        if not edges_path.exists():
            return jsonify({"error": f"Edges file not found at {edges_path}"}), 404

        return send_from_directory(
            str(edges_path.parent), edges_path.name, as_attachment=False
        )

    return jsonify({"error": "Invalid graph type"}), 404
