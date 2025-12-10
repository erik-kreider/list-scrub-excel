import argparse
import pathlib
import pandas as pd


def merge_excels(stems: list[str], input_dir: pathlib.Path, output_path: pathlib.Path):
    frames = []
    for stem in stems:
        path = input_dir / f"{stem}.xlsx"
        if not path.exists():
            raise FileNotFoundError(f"Missing chunk file: {path}")
        df = pd.read_excel(path)
        frames.append(df)
        print(f"Loaded {len(df):,} rows from {path}")
    merged = pd.concat(frames, ignore_index=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_excel(output_path, index=False)
    print(f"Merged {len(merged):,} rows -> {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Merge chunked Excel outputs into one file.")
    parser.add_argument("stems", nargs="+", help="Chunk stems (filenames without .xlsx), in desired order")
    parser.add_argument("--input-dir", default="lists", help="Directory containing chunk files (default: lists)")
    parser.add_argument("--output", required=True, help="Path for merged Excel output")
    args = parser.parse_args()

    input_dir = pathlib.Path(args.input_dir).expanduser().resolve()
    output_path = pathlib.Path(args.output).expanduser().resolve()

    merge_excels(args.stems, input_dir, output_path)


if __name__ == "__main__":
    main()
