import argparse
import logging
import sys

from dotenv import load_dotenv

from bugbug.generative_model_tool import create_llm
from bugbug.tools.code_review_generation import (
    CodeGeneratorTool,
    FixCommentDB,
    LocalQdrantVectorDB,
    generate_fixes,
)


def run(args) -> None:
    load_dotenv()

    logging.basicConfig(level=logging.INFO)

    db = FixCommentDB(LocalQdrantVectorDB(collection_name="fix_comments"))

    if args.create_db:
        db.db.delete_collection()
        db.db.setup()
        db.upload_dataset(args.dataset_file)

    llm = create_llm(args.llm)
    llm_tool = CodeGeneratorTool(llm=llm, db=db)

    generate_fixes(
        llm_tool=llm_tool,
        db=db,
        generation_limit=args.generation_limit,
        prompt_types=args.prompt_types,
        hunk_sizes=args.hunk_sizes,
        diff_length_limits=args.diff_length_limits,
        output_csv=args.output_csv,
    )


def parse_args(args):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--llm",
        help="LLM",
        choices=["openai"],
        default="openai",
    )
    parser.add_argument(
        "--create-db",
        action="store_true",
        help="If set, the local Qdrant database will be created and populated.",
    )
    parser.add_argument(
        "--output-csv",
        type=str,
        default="metrics_results.csv",
        help="Output CSV file for results.",
    )
    parser.add_argument(
        "--prompt-types",
        nargs="+",
        default=["zero-shot"],
        help="Types of prompts to use.",
    )
    parser.add_argument(
        "--diff-length-limits",
        nargs="+",
        type=int,
        default=[1000],
        help="Diff length limits to enforce when searching for examples.",
    )
    parser.add_argument(
        "--hunk-sizes",
        nargs="+",
        type=int,
        default=[20],
        help="Hunk sizes to enforce when searching for examples.",
    )
    parser.add_argument(
        "--generation-limit",
        type=int,
        default=100,
        help="Maximum number of generations.",
    )

    return parser.parse_args(args)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    run(args)
