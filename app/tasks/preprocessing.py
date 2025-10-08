import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import networkx as nx
import pandas as pd
from celery import shared_task, states
from celery.exceptions import Ignore
from loguru import logger

from app import db
from app.models import PreprocessingJob, UploadedFile

MIN_EDGE_WEIGHT = 40
MIN_COMPONENT_SIZE = 3


class TaskError(Exception):
    pass


def load_playlist_data(filepath: Path) -> tuple[pd.DataFrame, list[pd.Timestamp]]:
    """Load playlist track network data and generate time periods."""
    df = pd.read_parquet(filepath)
    start_date = df["thu_date"].min()
    end_date = df["thu_date"].max()
    time_period = list(pd.date_range(start=start_date, end=end_date, freq="W-THU"))
    return df, time_period


def songs_playlists_of_week(df: pd.DataFrame, week: pd.Timestamp) -> pd.DataFrame:
    """Get unique playlist-song combinations for a specific week."""
    weekly_data = df[df["thu_date"] == week.date()][
        ["playlist_id", "isrc"]
    ].drop_duplicates()
    return weekly_data


def find_new_playlist_additions(
    this_week: pd.DataFrame, next_week: pd.DataFrame
) -> pd.DataFrame:
    """Find song-playlist combinations that are new in the next week."""
    df_anti_join = pd.merge(
        next_week,
        this_week,
        how="outer",
        indicator=True,
        on=["isrc", "playlist_id"],
    )
    return df_anti_join[df_anti_join["_merge"] == "left_only"].drop("_merge", axis=1)


def calculate_song_transfers(
    songs_in_both: pd.DataFrame, new_in_next: pd.DataFrame
) -> pd.DataFrame:
    """Calculate song transfers between playlists."""
    song_transfers = pd.merge(
        songs_in_both,
        new_in_next,
        how="inner",
        on="isrc",
        suffixes=("_1", "_2"),
    )

    song_transfers_without_isrc = song_transfers.drop("isrc", axis=1)
    df_counts = (
        song_transfers_without_isrc.groupby(["playlist_id_1", "playlist_id_2"])
        .size()
        .reset_index(name="count")
    )
    return df_counts.sort_values(by="count", ascending=False)


def build_playlist_network(
    df: pd.DataFrame, time_period: list[pd.Timestamp], task=None
) -> nx.DiGraph:
    """Build a directed graph of playlist relationships based on song transfers."""
    graph: nx.DiGraph = nx.DiGraph()
    songs_playlists_next_week = None
    total_weeks = len(time_period)

    for i, week in enumerate(time_period[:]):
        if songs_playlists_next_week is not None:
            songs_playlists_this_week = songs_playlists_next_week
        else:
            songs_playlists_this_week = songs_playlists_of_week(df, week)

        next_week = week + timedelta(weeks=1)
        songs_playlists_next_week = songs_playlists_of_week(df, next_week)

        songs_playlists_in_both_weeks = pd.merge(
            songs_playlists_this_week,
            songs_playlists_next_week,
            how="inner",
            on=["isrc", "playlist_id"],
        )

        new_in_next_week = find_new_playlist_additions(
            songs_playlists_this_week, songs_playlists_next_week
        )
        new_in_next_week = new_in_next_week[
            new_in_next_week["isrc"].isin(songs_playlists_in_both_weeks["isrc"])
        ]

        df_counts = calculate_song_transfers(
            songs_playlists_in_both_weeks, new_in_next_week
        )
        pruned_transfers = df_counts[df_counts["count"] > MIN_EDGE_WEIGHT]

        graph.add_edges_from(
            [
                (playlist1, playlist2, {"weight": count})
                for playlist1, playlist2, count in pruned_transfers.itertuples(
                    index=False
                )
            ]
        )

        if task.is_aborted():
            logger.info(f"Task {task.request.id} aborted, stopping processing")
            raise Ignore

        # Update progress for Celery
        progress = int((i + 1) / total_weeks * 80) + 10  # 10-90% for this step
        task.update_state(
            state="PROGRESS",
            meta={
                "current": i + 1,
                "total": total_weeks,
                "percent": progress,
                "status": f"Processing week {i + 1}/{total_weeks}: {week.date()}",
            },
        )

    return graph


def prune_small_components(
    graph: nx.DiGraph, min_size: int = MIN_COMPONENT_SIZE
) -> nx.DiGraph:
    """Remove weakly connected components with few nodes."""
    for component in list(nx.weakly_connected_components(graph)):
        if len(component) <= min_size:
            graph.remove_nodes_from(component)
    return graph


def save_graph(
    graph: nx.DiGraph, basename: str, clean_data_dir: Path
) -> tuple[str, str]:
    """Save graph edges and nodes to CSV files."""
    number_of_nodes = graph.number_of_nodes()
    logger.info(f"Saving graph with {number_of_nodes} nodes")

    # Save edges
    edges_file = clean_data_dir / f"{basename}{number_of_nodes}_edges.csv"
    with Path.open(edges_file, "wb") as f:
        f.write(b"playlist_id_1,playlist_id_2,weight\n")
        nx.write_weighted_edgelist(graph, f, delimiter=",")

    # Save nodes
    nodes_file = clean_data_dir / f"{basename}_{number_of_nodes}_nodes.csv"
    with Path.open(nodes_file, "w") as f:
        f.write("playlist_id\n")
        f.writelines(f"{node}\n" for node in graph.nodes)

    return str(edges_file), str(nodes_file)


@shared_task(bind=True)
def preprocess_spotify_data_original(self, uuid: uuid.UUID):
    """
    Celery task using the exact same algorithm as create_data.py.
    """

    try:
        # Get the uploaded file record to create job
        uploaded_file = db.session.get(UploadedFile, str(uuid))

        if not uploaded_file:
            logger.error(f"No uploaded file found for uuid: {uuid}")

            self.update_state(
                state=states.FAILURE,
                meta={
                    "exc_type": "FileNotFoundError",
                    "exc_message": [f"File with uuid {uuid} not found in database"],
                    "status": "error",
                },
            )
            raise FileNotFoundError(f"File with uuid {uuid} not found in database")

        # Create preprocessing job record
        job = PreprocessingJob(
            task_id=self.request.id,
            file_uuid=uploaded_file.uuid,
            status="processing",
        )  # type: ignore
        db.session.add(job)
        db.session.commit()

        logger.info(f"Created and started processing job {job.uuid} for file {uuid}")
        # Set up paths using Flask app configuration
        from flask import current_app

        upload_folder = Path(current_app.root_path).parent / "uploads"
        preprocessed_data_dir = current_app.config.get(
            "PREPROCESSED_DATA_DIR", "preprocessed"
        )
        preprocessed_data_directory = (
            Path(current_app.static_folder) / preprocessed_data_dir  # type: ignore
        )
        preprocessed_data_directory.mkdir(exist_ok=True)

        input_filepath = upload_folder / (str(uuid) + ".parquet")

        if not input_filepath.exists():
            if job:
                job.status = "failed"
                job.error_message = f"File {str(uuid) + '.parquet'} not found"
                job.completed_at = datetime.now(UTC)
                db.session.commit()

            self.update_state(
                state=states.FAILURE,
                meta={
                    "exc_type": "FileNotFoundError",
                    "exc_message": [f"File {str(uuid) + '.parquet'} not found"],
                    "status": "error",
                },
            )
            raise FileNotFoundError(f"File {str(uuid) + '.parquet'} not on disk")

        logger.info(
            f"Starting original algorithm preprocessing of {str(uuid) + '.parquet'}"
        )

        self.update_state(
            state="PROGRESS",
            meta={
                "current": 0,
                "total": 100,
                "percent": 0,
                "status": "Loading playlist data...",
            },
        )

        # Load data (exact same as original)
        df_playlist_track_network, time_period = load_playlist_data(input_filepath)

        logger.info(f"Loaded {len(df_playlist_track_network):,} rows")
        logger.info(f"Found {len(time_period)} time periods")

        self.update_state(
            state="PROGRESS",
            meta={
                "current": 10,
                "total": 100,
                "percent": 10,
                "status": f"Building network graph ({len(time_period)} weeks)...",
            },
        )

        # Build graph (exact same as original)
        graph = build_playlist_network(
            df_playlist_track_network, time_period, task=self
        )

        logger.info(
            f"Built graph with {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges"
        )

        self.update_state(
            state="PROGRESS",
            meta={
                "current": 90,
                "total": 100,
                "percent": 90,
                "status": "Saving initial graph and pruning...",
            },
        )

        # Prune small components (exact same as original)
        initial_nodes = graph.number_of_nodes()
        initial_edges = graph.number_of_edges()
        graph = prune_small_components(graph)

        # Save pruned graph (exact same as original)
        edges_file, nodes_file = save_graph(
            graph, "pruned_graph", preprocessed_data_directory
        )

        # Update job record with results
        if job:
            logger.info(f"Updating job {job.uuid} status to completed")
            job.status = "completed"
            job.completed_at = datetime.now(UTC)
            # Store relative paths from static directory
            job.edges_file = f"{Path(edges_file).name}"
            job.nodes_file = f"{Path(nodes_file).name}"
            job.final_nodes = graph.number_of_nodes()
            job.final_edges = graph.number_of_edges()
            job.time_periods = len(time_period)
            db.session.commit()
            logger.info(
                f"Job {job.uuid} status updated to completed with {job.final_nodes} nodes and {job.final_edges} edges"
            )

        # Final statistics
        # Check if graph is empty before connectivity checks
        is_weakly = False
        is_strongly = False
        if graph.number_of_nodes() > 0:
            is_weakly = nx.is_weakly_connected(graph)
            is_strongly = nx.is_strongly_connected(graph)

        result = {
            "status": "success",
            "input_file": str(uuid) + ".parquet",
            "output_files": {
                "edges": edges_file,
                "nodes": nodes_file,
            },
            "statistics": {
                "initial_nodes": initial_nodes,
                "initial_edges": initial_edges,
                "final_nodes": graph.number_of_nodes(),
                "final_edges": graph.number_of_edges(),
                "directed": nx.is_directed(graph),
                "weakly_connected": is_weakly,
                "strongly_connected": is_strongly,
                "time_periods": len(time_period),
            },
        }

        self.update_state(
            state=states.SUCCESS,
            meta={
                "current": 100,
                "total": 100,
                "percent": 100,
                "status": "Processing complete!",
                "result": result,
            },
        )

        logger.info("Original algorithm preprocessing completed successfully")
        return result

    except Ignore:
        if job:
            job.status = "cancelled"
            job.error_message = "Task cancelled by user"
            job.completed_at = datetime.now(UTC)
            db.session.commit()
            logger.info(f"Job {job.uuid} status updated to cancelled")
    except FileNotFoundError:
        self.update_state(
            state=states.FAILURE,
        )
        raise TaskError(f"File with uuid {uuid} not found in database") from None

    except Exception as e:
        logger.error(f"Error in original preprocessing: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())
        self.update_state(
            state=states.FAILURE,
            meta={
                "exc_type": type(e).__name__,
                "exc_message": [str(e)],
                "status": "error",
            },
        )
        raise Ignore from None
