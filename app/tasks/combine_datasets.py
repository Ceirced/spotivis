"""Celery task for combining two preprocessed datasets."""

from datetime import datetime
from pathlib import Path

import pandas as pd
from celery import shared_task
from flask import current_app
from loguru import logger
from sqlalchemy import select

from app import create_app, db
from app.models import CombinedPreprocessingJob


@shared_task(bind=True)
def combine_preprocessed_datasets(self, combined_job_id: str):
    """
    Combine two preprocessed datasets, preserving time period information.

    Args:
        combined_job_id: UUID of the CombinedPreprocessingJob record
    """
    app = create_app()
    with app.app_context():
        try:
            # Get the combined job record
            stmt = select(CombinedPreprocessingJob).where(
                CombinedPreprocessingJob.uuid == combined_job_id
            )
            combined_job = db.session.scalar(stmt)

            if not combined_job:
                logger.error(f"Combined job {combined_job_id} not found")
                return {"status": "error", "error": "Combined job not found"}

            # Update task status
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": 10,
                    "total": 100,
                    "status": "Loading first dataset...",
                    "percent": 10,
                },
            )

            # Get the preprocessing jobs
            first_job = combined_job.first_job
            second_job = combined_job.second_job

            if not first_job or not second_job:
                raise ValueError("Invalid preprocessing jobs")

            # Get file paths
            preprocessed_data_dir = current_app.config.get(
                "PREPROCESSED_DATA_DIR", "preprocessed"
            )
            static_folder = Path(current_app.static_folder)  # type: ignore

            # Load first dataset
            first_nodes_path = (
                static_folder / preprocessed_data_dir / first_job.nodes_file
            )
            first_edges_path = (
                static_folder / preprocessed_data_dir / first_job.edges_file
            )

            if not first_nodes_path.exists() or not first_edges_path.exists():
                raise FileNotFoundError("First dataset files not found")

            first_nodes_df = pd.read_csv(first_nodes_path)
            first_edges_df = pd.read_csv(first_edges_path)

            # Add time period marker to first dataset
            first_nodes_df["time_period"] = "old"
            first_nodes_df["dataset_source"] = "first"
            first_edges_df["dataset_source"] = "first"

            self.update_state(
                state="PROGRESS",
                meta={
                    "current": 30,
                    "total": 100,
                    "status": "Loading second dataset...",
                    "percent": 30,
                },
            )

            # Load second dataset
            second_nodes_path = (
                static_folder / preprocessed_data_dir / second_job.nodes_file
            )
            second_edges_path = (
                static_folder / preprocessed_data_dir / second_job.edges_file
            )

            if not second_nodes_path.exists() or not second_edges_path.exists():
                raise FileNotFoundError("Second dataset files not found")

            second_nodes_df = pd.read_csv(second_nodes_path)
            second_edges_df = pd.read_csv(second_edges_path)

            # Add time period marker to second dataset
            second_nodes_df["time_period"] = "new"
            second_nodes_df["dataset_source"] = "second"
            second_edges_df["dataset_source"] = "second"

            self.update_state(
                state="PROGRESS",
                meta={
                    "current": 50,
                    "total": 100,
                    "status": "Combining datasets...",
                    "percent": 50,
                },
            )

            # Identify nodes that exist in both datasets
            # Use 'playlist_id' as the node identifier
            first_node_ids = set(first_nodes_df["playlist_id"])
            second_node_ids = set(second_nodes_df["playlist_id"])

            # Nodes that exist in both periods
            common_node_ids = first_node_ids & second_node_ids

            # Nodes only in first (old) dataset
            old_only_ids = first_node_ids - second_node_ids

            # Nodes only in second (new) dataset
            new_only_ids = second_node_ids - first_node_ids

            # Update time_period for common nodes
            first_nodes_df.loc[
                first_nodes_df["playlist_id"].isin(common_node_ids), "time_period"
            ] = "both"
            second_nodes_df.loc[
                second_nodes_df["playlist_id"].isin(common_node_ids), "time_period"
            ] = "both"

            # Combine nodes - for common nodes, keep the one from the second (newer) dataset
            # but mark them as existing in both periods
            combined_nodes_df = pd.concat(
                [
                    first_nodes_df[first_nodes_df["playlist_id"].isin(old_only_ids)],
                    second_nodes_df[
                        second_nodes_df["playlist_id"].isin(
                            new_only_ids | common_node_ids
                        )
                    ],
                ],
                ignore_index=True,
            )

            # Remove duplicate columns if any
            combined_nodes_df = combined_nodes_df.loc[
                :, ~combined_nodes_df.columns.duplicated()
            ]

            # Combine edges - keep all unique edges
            combined_edges_df = pd.concat(
                [first_edges_df, second_edges_df], ignore_index=True
            )

            # Remove duplicate edges (same playlist_id_1 and playlist_id_2)
            combined_edges_df = combined_edges_df.drop_duplicates(
                subset=["playlist_id_1", "playlist_id_2"], keep="last"
            )

            self.update_state(
                state="PROGRESS",
                meta={
                    "current": 70,
                    "total": 100,
                    "status": "Saving combined dataset...",
                    "percent": 70,
                },
            )

            # Generate output filenames
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            combined_job_uuid_short = str(combined_job.uuid)[:8]

            nodes_filename = f"combined_nodes_{combined_job_uuid_short}_{timestamp}.csv"
            edges_filename = f"combined_edges_{combined_job_uuid_short}_{timestamp}.csv"

            # Save combined files
            output_dir = static_folder / preprocessed_data_dir
            output_dir.mkdir(parents=True, exist_ok=True)

            nodes_output_path = output_dir / nodes_filename
            edges_output_path = output_dir / edges_filename

            combined_nodes_df.to_csv(nodes_output_path, index=False)
            combined_edges_df.to_csv(edges_output_path, index=False)

            self.update_state(
                state="PROGRESS",
                meta={
                    "current": 90,
                    "total": 100,
                    "status": "Updating database...",
                    "percent": 90,
                },
            )

            # Extract date ranges from original parquet files if available
            first_file = first_job.uploaded_file
            second_file = second_job.uploaded_file

            # Try to get date ranges from the original files
            upload_folder = Path(current_app.root_path).parent / "uploads"

            try:
                import pyarrow.parquet as pq

                # First file date range
                first_parquet_path = upload_folder / first_file.filename
                if first_parquet_path.exists():
                    first_parquet = pq.ParquetFile(str(first_parquet_path))
                    first_dates = first_parquet.read(columns=["thu_date"]).to_pandas()[
                        "thu_date"
                    ]
                    first_dates = pd.to_datetime(first_dates)
                    combined_job.first_start_date = first_dates.min()
                    combined_job.first_end_date = first_dates.max()

                # Second file date range
                second_parquet_path = upload_folder / second_file.filename
                if second_parquet_path.exists():
                    second_parquet = pq.ParquetFile(str(second_parquet_path))
                    second_dates = second_parquet.read(
                        columns=["thu_date"]
                    ).to_pandas()["thu_date"]
                    second_dates = pd.to_datetime(second_dates)
                    combined_job.second_start_date = second_dates.min()
                    combined_job.second_end_date = second_dates.max()
            except Exception as e:
                logger.warning(f"Could not extract date ranges: {e}")

            # Update the combined job record
            combined_job.status = "completed"
            combined_job.completed_at = datetime.utcnow()
            combined_job.nodes_file = nodes_filename
            combined_job.edges_file = edges_filename
            combined_job.total_nodes = len(combined_nodes_df)
            combined_job.total_edges = len(combined_edges_df)
            combined_job.nodes_from_first = len(old_only_ids)
            combined_job.nodes_from_second = len(new_only_ids)
            combined_job.new_nodes = len(new_only_ids)

            db.session.commit()

            logger.info(
                f"Successfully combined datasets: "
                f"{combined_job.total_nodes} nodes, {combined_job.total_edges} edges"
            )

            # Set final success state with results
            self.update_state(
                state="SUCCESS",
                meta={
                    "current": 100,
                    "total": 100,
                    "status": "Complete!",
                    "percent": 100,
                    "result": {
                        "combined_job_id": combined_job_id,
                        "total_nodes": combined_job.total_nodes,
                        "total_edges": combined_job.total_edges,
                        "nodes_from_first": combined_job.nodes_from_first,
                        "nodes_from_second": combined_job.nodes_from_second,
                        "common_nodes": len(common_node_ids),
                    },
                },
            )

            return {
                "status": "success",
                "result": {
                    "combined_job_id": combined_job_id,
                    "total_nodes": combined_job.total_nodes,
                    "total_edges": combined_job.total_edges,
                    "nodes_from_first": combined_job.nodes_from_first,
                    "nodes_from_second": combined_job.nodes_from_second,
                    "common_nodes": len(common_node_ids),
                },
            }

        except Exception as e:
            logger.error(f"Error combining datasets: {e}")

            # Update job status
            if combined_job:
                combined_job.status = "failed"
                combined_job.completed_at = datetime.utcnow()
                combined_job.error_message = str(e)
                db.session.commit()

            return {"status": "error", "error": str(e)}
