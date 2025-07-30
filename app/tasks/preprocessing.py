from datetime import timedelta
from pathlib import Path
from typing import List, Tuple
import gc

import networkx as nx
import pandas as pd
from celery import shared_task
from loguru import logger

MIN_EDGE_WEIGHT = 40
MIN_COMPONENT_SIZE = 3


def load_playlist_data(filepath: Path) -> Tuple[pd.DataFrame, List[pd.Timestamp]]:
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
    df: pd.DataFrame, time_period: List[pd.Timestamp], task=None
) -> nx.DiGraph:
    """Build a directed graph of playlist relationships based on song transfers."""
    G: nx.DiGraph = nx.DiGraph()
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

        G.add_edges_from(
            [
                (playlist1, playlist2, {"weight": count})
                for playlist1, playlist2, count in pruned_transfers.itertuples(
                    index=False
                )
            ]
        )

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

        # Clean up memory periodically
        if i % 10 == 0:
            gc.collect()

    return G


def prune_small_components(
    G: nx.DiGraph, min_size: int = MIN_COMPONENT_SIZE
) -> nx.DiGraph:
    """Remove weakly connected components with few nodes."""
    for component in list(nx.weakly_connected_components(G)):
        if len(component) <= min_size:
            G.remove_nodes_from(component)
    return G


def save_graph(
    graph: nx.DiGraph, basename: str, clean_data_dir: Path
) -> Tuple[str, str]:
    """Save graph edges and nodes to CSV files."""
    number_of_nodes = graph.number_of_nodes()
    logger.info(f"Saving graph with {number_of_nodes} nodes")

    # Save edges
    edges_file = clean_data_dir / f"{basename}{number_of_nodes}_edges.csv"
    with open(edges_file, "wb") as f:
        f.write(b"playlist_id_1,playlist_id_2,weight\n")
        nx.write_weighted_edgelist(graph, f, delimiter=",")

    # Save nodes
    nodes_file = clean_data_dir / f"{basename}_{number_of_nodes}_nodes.csv"
    with open(nodes_file, "w") as f:
        f.write("playlist_id\n")
        for node in graph.nodes:
            f.write(f"{node}\n")

    return str(edges_file), str(nodes_file)


@shared_task(bind=True)
def preprocess_spotify_data_original(self, filename: str):
    """
    Celery task using the exact same algorithm as create_data.py.
    """
    try:
        # Set up paths
        upload_folder = Path("/home/app/uploads")
        clean_data_dir = Path("/home/app/clean_data")
        clean_data_dir.mkdir(exist_ok=True)

        input_filepath = upload_folder / filename

        if not input_filepath.exists():
            return {"status": "error", "error": f"File {filename} not found"}

        logger.info(f"Starting original algorithm preprocessing of {filename}")

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
        G = build_playlist_network(df_playlist_track_network, time_period, task=self)

        logger.info(
            f"Built graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges"
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
        initial_nodes = G.number_of_nodes()
        initial_edges = G.number_of_edges()
        G = prune_small_components(G)

        # Save pruned graph (exact same as original)
        edges_file, nodes_file = save_graph(G, "pruned_graph", clean_data_dir)

        # Final statistics
        result = {
            "status": "success",
            "input_file": filename,
            "output_files": {
                "edges": edges_file,
                "nodes": nodes_file,
            },
            "statistics": {
                "initial_nodes": initial_nodes,
                "initial_edges": initial_edges,
                "final_nodes": G.number_of_nodes(),
                "final_edges": G.number_of_edges(),
                "directed": nx.is_directed(G),
                "weakly_connected": nx.is_weakly_connected(G),
                "strongly_connected": nx.is_strongly_connected(G),
                "time_periods": len(time_period),
            },
        }

        self.update_state(
            state="SUCCESS",
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

    except Exception as e:
        logger.error(f"Error in original preprocessing: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "error": str(e),
        }
