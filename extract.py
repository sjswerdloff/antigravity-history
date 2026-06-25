import os
from antigravity_history.cli_parser import export_session

if __name__ == "__main__":
    transcript_file = os.path.expanduser("~/.gemini/antigravity-cli/brain/3355b4df-cc7f-4075-b4a7-4950caf7f0b4/.system_generated/logs/transcript_full.jsonl")
    output_file = os.path.expanduser("~/ai/ClaudeInstanceHomeOffices/paxton-55a34233/json_memories/antigravity/conversations_export.json")
    cascade_id = "3355b4df-cc7f-4075-b4a7-4950caf7f0b4"
    
    export_session(transcript_file, output_file, cascade_id)
