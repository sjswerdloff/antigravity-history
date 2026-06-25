import sys
from antigravity_history.cli_parser import export_session

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python extract.py <transcript_jsonl> <output_json> <cascade_id>")
        sys.exit(1)

    transcript_file = sys.argv[1]
    output_file = sys.argv[2]
    cascade_id = sys.argv[3]

    export_session(transcript_file, output_file, cascade_id)
