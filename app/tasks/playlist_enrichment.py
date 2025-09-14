from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import spotipy
from celery import shared_task
from loguru import logger
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyClientCredentials
from sqlalchemy import select

from app import db
from app.models import PlaylistEnrichmentJob, PreprocessingJob


@shared_task(bind=True)
def enrich_playlist_nodes(self, preprocessing_job_uuid: str):
    """
    Celery task to enrich playlist nodes with Spotify API data.
    Fetches playlist name, description, and follower count for each playlist ID.
    """

    try:
        # Create enrichment job record
        job = PlaylistEnrichmentJob(
            preprocessing_job_id=preprocessing_job_uuid,
            task_id=self.request.id,
            status="processing",
        )  # type: ignore
        db.session.add(job)
        db.session.commit()

        logger.info(
            f"Created and started enrichment job {job.uuid} for preprocessing job {preprocessing_job_uuid}"
        )

        # Get the preprocessing job to find the nodes file
        stmt = select(PreprocessingJob).where(
            PreprocessingJob.uuid == preprocessing_job_uuid
        )
        preprocessing_job = db.session.scalar(stmt)

        if not preprocessing_job or not preprocessing_job.nodes_file:
            logger.error(
                f"No preprocessing job or nodes file found for UUID: {preprocessing_job_uuid}"
            )
            job.status = "failed"
            job.error_message = "Preprocessing job or nodes file not found"
            job.completed_at = datetime.now(UTC)
            db.session.commit()
            return {
                "status": "error",
                "error": "Preprocessing job or nodes file not found",
            }

        # Set up paths
        from flask import current_app

        preprocessed_data_dir = current_app.config.get(
            "PREPROCESSED_DATA_DIR", "preprocessed"
        )
        preprocessed_data_directory = (
            Path(current_app.static_folder) / preprocessed_data_dir  # type: ignore
        )

        nodes_file_path = preprocessed_data_directory / preprocessing_job.nodes_file

        if not nodes_file_path.exists():
            job.status = "failed"
            job.error_message = f"Nodes file not found: {nodes_file_path}"
            job.completed_at = datetime.now(UTC)
            db.session.commit()
            return {
                "status": "error",
                "error": f"Nodes file not found: {nodes_file_path}",
            }

        logger.info(f"Starting enrichment of playlists from {nodes_file_path}")

        # Initialize Spotify client with client credentials flow
        import os

        client_id = os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

        if not client_id or not client_secret:
            error_msg = "Spotify API credentials not found in environment variables"
            logger.error(error_msg)
            job.status = "failed"
            job.error_message = error_msg
            job.completed_at = datetime.now(UTC)
            db.session.commit()
            return {"status": "error", "error": error_msg}

        # Use client credentials flow - no user authentication needed
        client_credentials_manager = SpotifyClientCredentials(
            client_id=client_id, client_secret=client_secret
        )
        sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

        # Load playlist IDs from nodes file
        self.update_state(
            state="PROGRESS",
            meta={
                "current": 0,
                "total": 100,
                "percent": 0,
                "status": "Loading playlist IDs...",
                "found": 0,
                "not_found": 0,
            },
        )

        df_nodes = pd.read_csv(nodes_file_path)
        playlist_ids = df_nodes["playlist_id"].tolist()
        total_playlists = len(playlist_ids)

        logger.info(f"Found {total_playlists} playlists to enrich")

        # Prepare enriched data
        enriched_data = []
        found_count = 0
        not_found_count = 0

        for idx, playlist_id in enumerate(playlist_ids):
            try:
                # Fetch playlist data from Spotify API
                playlist = sp.playlist(
                    playlist_id, fields="name,description,followers,owner"
                )

                enriched_data.append(
                    {
                        "playlist_id": playlist_id,
                        "display_name": playlist.get("name", ""),
                        "playlist_description": playlist.get("description", ""),
                        "playlist_followers": playlist.get("followers", {}).get(
                            "total", 0
                        ),
                        "owner_display_name": playlist.get("owner", {}).get(
                            "display_name", ""
                        ),
                    }
                )
                found_count += 1

            except SpotifyException as e:
                # Playlist not found or other API error
                logger.warning(f"Failed to fetch playlist {playlist_id}: {e}")
                enriched_data.append(
                    {
                        "playlist_id": playlist_id,
                        "display_name": None,
                        "playlist_description": None,
                        "playlist_followers": None,
                        "owner_display_name": None,
                    }
                )
                not_found_count += 1

            # Update progress
            progress = int((idx + 1) / total_playlists * 100)
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": idx + 1,
                    "total": total_playlists,
                    "percent": progress,
                    "status": f"Processing playlist {idx + 1}/{total_playlists}",
                    "found": found_count,
                    "not_found": not_found_count,
                },
            )

        # Save enriched data to CSV - overwrite the original nodes file
        enriched_df = pd.DataFrame(enriched_data)

        # Save to the same location as the original nodes file
        output_path = nodes_file_path
        output_filename = preprocessing_job.nodes_file

        # Backup original file first
        backup_path = nodes_file_path.with_suffix(".csv.bak")
        import shutil

        shutil.copy2(nodes_file_path, backup_path)

        enriched_df.to_csv(output_path, index=False)

        logger.info(
            f"Saved enriched data to {output_path} (backed up original to {backup_path})"
        )

        # Update job record with results
        job.status = "completed"
        job.completed_at = datetime.now(UTC)
        job.output_file = output_filename
        job.total_playlists = total_playlists
        job.found_count = found_count
        job.not_found_count = not_found_count
        db.session.commit()

        result = {
            "status": "success",
            "output_file": output_filename,
            "job_uuid": str(job.uuid),
            "statistics": {
                "total_playlists": total_playlists,
                "found": found_count,
                "not_found": not_found_count,
            },
        }

        self.update_state(
            state="SUCCESS",
            meta={
                "current": total_playlists,
                "total": total_playlists,
                "percent": 100,
                "status": "Enrichment complete!",
                "found": found_count,
                "not_found": not_found_count,
                "result": result,
            },
        )

        logger.info(
            f"Enrichment completed successfully: {found_count} found, {not_found_count} not found"
        )
        return result

    except Exception as e:
        logger.error(f"Error in playlist enrichment: {str(e)}")
        import traceback

        logger.error(traceback.format_exc())

        # Update job record with error
        try:
            if job:
                job.status = "failed"
                job.error_message = str(e)
                job.completed_at = datetime.now(UTC)
                db.session.commit()
        except Exception as commit_error:
            logger.error(f"Failed to update job status to failed: {commit_error}")

        return {
            "status": "error",
            "error": str(e),
        }
