from datetime import timedelta
from pathlib import Path
from typing import List, Tuple

import networkx as nx
import pandas as pd
from loguru import logger
from tqdm import tqdm

RAW_DATA_DIR = Path("uploads")
CLEAN_DATA_DIR = Path("clean_data")

# Constants
MIN_EDGE_WEIGHT = 40
MIN_COMPONENT_SIZE = 3
PLAYLIST_TRACK_NETWORK_FILE = RAW_DATA_DIR / "playlist_track_network.parquet"


def load_playlist_data() -> Tuple[pd.DataFrame, List[pd.Timestamp]]:
    """Load playlist track network data and generate time periods."""
    df = pd.read_parquet(PLAYLIST_TRACK_NETWORK_FILE)
    start_date = df["thu_date"].min()
    end_date = df["thu_date"].max()
    time_period = list(pd.date_range(start=start_date, end=end_date, freq="W-THU"))
    return df, time_period


def assert_no_common_rows(df1: pd.DataFrame, df2: pd.DataFrame) -> None:
    common_rows = df1.merge(df2, how="inner", on=["isrc", "playlist_id"])
    assert common_rows.empty, "Some rows appear in both dataframes"


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
    df: pd.DataFrame, time_period: List[pd.Timestamp]
) -> nx.DiGraph:
    """Build a directed graph of playlist relationships based on song transfers."""
    G: nx.DiGraph = nx.DiGraph()
    songs_playlists_next_week = None

    for week in tqdm(time_period[:]):
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

        assert_no_common_rows(new_in_next_week, songs_playlists_in_both_weeks)
        assert_no_common_rows(new_in_next_week, songs_playlists_this_week)

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

    return G


def prune_small_components(
    G: nx.DiGraph, min_size: int = MIN_COMPONENT_SIZE
) -> nx.DiGraph:
    """Remove weakly connected components with few nodes."""
    for component in list(nx.weakly_connected_components(G)):
        if len(component) <= min_size:
            G.remove_nodes_from(component)
    return G


def save_graph(graph: nx.DiGraph, basename: str) -> None:
    """Save graph edges and nodes to CSV files."""
    number_of_nodes = graph.number_of_nodes()
    logger.info(f"Saving graph with {number_of_nodes} nodes")

    # Save edges
    edges_file = CLEAN_DATA_DIR / f"{basename}{number_of_nodes}_edges.csv"
    with open(edges_file, "wb") as f:
        f.write(b"playlist_id_1,playlist_id_2,weight\n")
        nx.write_weighted_edgelist(graph, f, delimiter=",")

    # Save nodes
    nodes_file = CLEAN_DATA_DIR / f"{basename}_{number_of_nodes}_nodes.csv"
    with open(nodes_file, "w") as f:
        f.write("playlist_id\n")
        for node in graph.nodes:
            f.write(f"{node}\n")


def print_graph_info(G: nx.DiGraph) -> None:
    """Print basic information about the graph."""
    print(f"Directed: {nx.is_directed(G)}")
    print(f"Weakly connected: {nx.is_weakly_connected(G)}")
    print(f"Strongly connected: {nx.is_strongly_connected(G)}")
    print(f"Number of nodes: {G.number_of_nodes()}")
    print(f"Number of edges: {G.number_of_edges()}")


def main():
    """Main function to create playlist network graph."""
    # Load data
    df_playlist_track_network, time_period = load_playlist_data()

    # Build graph
    G = build_playlist_network(df_playlist_track_network, time_period)

    # Save initial graph
    nx.write_gml(G, CLEAN_DATA_DIR / f"playlist_{G.number_of_nodes()}_graph.gml")

    # Prune small components
    G = prune_small_components(G)

    # Print graph information
    print_graph_info(G)

    # Save pruned graph
    save_graph(G, "pruned_graph")


if __name__ == "__main__":
    main()
