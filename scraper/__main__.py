import argparse
from .runner import run


def main():
    parser = argparse.ArgumentParser(description="Upwork job scraper")
    parser.add_argument("keywords", nargs="+", help="Search keywords")
    parser.add_argument("--output", default="./data/jobs.csv", help="Output CSV path")
    parser.add_argument("--max-jobs", type=int, default=100, help="Max jobs to scrape")
    parser.add_argument("--debug", action="store_true",
                        help="Dump page structure of first job to ./data/debug_dump.json")
    args = parser.parse_args()

    run(
        query=" ".join(args.keywords),
        output_path=args.output,
        max_jobs=args.max_jobs,
        debug=args.debug,
    )


if __name__ == "__main__":
    main()
