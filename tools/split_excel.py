import argparse
import math
import pathlib
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


def main():
    parser = argparse.ArgumentParser(description="Split a large Excel file into chunks.")
    parser.add_argument("source", type=str, help="Path to the source Excel file")
    parser.add_argument("--chunk-size", type=int, default=20000, help="Rows per chunk (default: 20000)")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory (default: same as source)")
    args = parser.parse_args()

    src = pathlib.Path(args.source).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(f"Source file not found: {src}")

    out_dir = pathlib.Path(args.output_dir).expanduser().resolve() if args.output_dir else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    stems = split_excel(src, args.chunk_size, out_dir)
    print("Chunk stems (use as filenames without .xlsx):")
    for stem in stems:
        print(stem)


if __name__ == "__main__":
    main()
