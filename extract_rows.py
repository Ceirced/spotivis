#!/usr/bin/env python3
"""
Script to extract the first n rows from a parquet file.
Usage: python extract_rows.py <n_rows> [input_file] [output_file]
"""

import argparse
import sys
from pathlib import Path

import pyarrow.parquet as pq


def extract_first_n_rows(input_file: Path, output_file: Path, n_rows: int) -> None:
    """
    Extract the first n rows from a parquet file and save to a new file.

    Args:
        input_file: Path to input parquet file
        output_file: Path to output parquet file
        n_rows: Number of rows to extract
    """
    try:
        table = pq.read_table(input_file)

        total_rows = table.num_rows
        print(
            f"Original file has {total_rows} rows and {len(table.column_names)} columns"
        )

        if n_rows > total_rows:
            print(
                f"Warning: Requested {n_rows} rows but file only has {total_rows}. Using all rows."
            )
            n_rows = total_rows
        elif n_rows <= 0:
            raise ValueError("Number of rows must be positive")

        print(f"\nExtracting first {n_rows} rows...")

        subset_table = table.slice(0, n_rows)

        pq.write_table(subset_table, output_file)

        original_size = input_file.stat().st_size / 1024
        new_size = output_file.stat().st_size / 1024
        reduction = (
            ((original_size - new_size) / original_size) * 100
            if original_size > 0
            else 0
        )

        print(f"\nSuccessfully wrote {n_rows} rows to {output_file}")
        print(f"Original file size: {original_size:.2f} KB")
        print(f"Output file size: {new_size:.2f} KB")
        print(f"Size reduction: {reduction:.1f}%")
        print(f"Columns preserved: {len(subset_table.column_names)}")

    except Exception as e:
        print(f"Error processing parquet file: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Extract first n rows from a parquet file"
    )
    parser.add_argument(
        "n_rows", type=int, help="Number of rows to extract from the beginning"
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        help="Input parquet file path (default: raw_data/playlist_track_network.parquet)",
    )
    parser.add_argument(
        "output_file",
        nargs="?",
        help="Output parquet file path (default: input_file with '_<n_rows>_rows' suffix)",
    )

    args = parser.parse_args()

    if args.input_file:
        input_path = Path(args.input_file)
    else:
        input_path = Path("raw_data/playlist_track_network.parquet")
        print(f"Using default input file: {input_path}")

    if not input_path.exists():
        print(f"Error: Input file '{input_path}' does not exist", file=sys.stderr)
        sys.exit(1)

    if not input_path.suffix == ".parquet":
        print("Error: Input file must be a .parquet file", file=sys.stderr)
        sys.exit(1)

    if args.output_file:
        output_path = Path(args.output_file)
    else:
        output_path = (
            input_path.parent / f"{input_path.stem}_{args.n_rows}_rows.parquet"
        )
        print(f"Using default output file: {output_path}")

    extract_first_n_rows(input_path, output_path, args.n_rows)


if __name__ == "__main__":
    main()
