import argparse
import math
import pathlib
import subprocess
import sys
import pandas as pd


def split_excel(path: pathlib.Path, chunk_size: int, output_dir: pathlib.Path):
    df = pd.read_excel(path)
    total = len(df)
    parts = math.ceil(total / chunk_size)
    stems = []
    for i in range(parts):
        part = df.iloc[i * chunk_size : (i + 1) * chunk_size]
        out_name = f"{path.stem}_part{i+1}.xlsx"
        out_path = output_dir / out_name
        part.to_excel(out_path, index=False)
        stems.append(path.stem + f"_part{i+1}")
        print(f"Wrote {len(part):,} rows to {out_path}")
    return stems


def merge_outputs(stems: list[str], output_dir: pathlib.Path, merged_path: pathlib.Path):
    frames = []
    for stem in stems:
        path = output_dir / f"{stem}.xlsx"
        if not path.exists():
            raise FileNotFoundError(f"Missing output chunk: {path}")
        df = pd.read_excel(path)
        frames.append(df)
        print(f"Loaded {len(df):,} rows from {path}")
    merged = pd.concat(frames, ignore_index=True)
    merged_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_excel(merged_path, index=False)
    print(f"Merged {len(merged):,} rows -> {merged_path}")


def main():
    parser = argparse.ArgumentParser(description="Split a large Excel, scrub each chunk, then merge outputs.")
    parser.add_argument("source", help="Path to the source Excel file to scrub (without .xlsx extension not required)")
    parser.add_argument("--chunk-size", type=int, default=20000, help="Rows per chunk (default: 20000)")
    parser.add_argument(
        "--output",
        help="Merged output path (default: <source_stem>_MERGED_OUTPUT.xlsx in source directory)",
    )
    args = parser.parse_args()

    src = pathlib.Path(args.source)
    if src.suffix.lower() != ".xlsx":
        src = src.with_suffix(".xlsx")
    src = src.expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(f"Source file not found: {src}")

    out_dir = src.parent
    merged_output = (
        pathlib.Path(args.output).expanduser().resolve()
        if args.output
        else out_dir / f"{src.stem}_MERGED_OUTPUT.xlsx"
    )

    print(f"Splitting {src} into ~{args.chunk_size}-row parts...")
    stems = split_excel(src, args.chunk_size, out_dir)

    print("Running account scrub on each chunk...")
    for stem in stems:
        cmd = [sys.executable, "main.py", "account", stem]
        print(f" -> {' '.join(cmd)}")
        subprocess.run(cmd, check=True)

    output_stems = [stem + "_OUTPUT" for stem in stems]
    print("Merging chunk outputs...")
    merge_outputs(output_stems, out_dir, merged_output)
    print("Done.")


if __name__ == "__main__":
    main()
