import json
import re
from typing import Dict, List, Any, Tuple

# Regexes for extracting person_id
msg_regex = re.compile(r"You have a new message from ([a-z0-9\-]+)\. Please read file")
file_msg_regex = re.compile(r"From: ([a-z0-9\-]+) at ")

class TranscriptParserError(Exception):
    pass

def parse_transcript_line(line: str) -> Tuple[Dict[str, Any] | None, bool]:
    """Parse a single JSONL line into a message dict. Returns (msg, is_error)."""
    try:
        step = json.loads(line)
    except json.JSONDecodeError:
        return None, True
        
    source = step.get("source", "")
    step_type = step.get("type", "")
    content = step.get("content", "")
    timestamp = step.get("created_at", "")
    thinking = step.get("thinking", "")
    tool_calls = step.get("tool_calls", [])
    
    role = None
    if source == "USER_EXPLICIT":
        role = "user"
    elif source == "MODEL":
        if step_type == "PLANNER_RESPONSE":
            role = "assistant"
        else:
            role = "tool"
    elif source == "SYSTEM":
        if step_type in ["EPHEMERAL_MESSAGE", "CHECKPOINT", "CONVERSATION_HISTORY"]:
            return None, False # Skip gracefully
        role = "tool"
        
    if role is None:
        return None, True # Unknown role mapping is an error

    if not content and tool_calls:
        content = json.dumps(tool_calls, indent=2)
        
    if not content and not thinking:
        return None, False # Nothing to ingest
        
    msg = {"role": role, "content": content, "timestamp": timestamp}
    
    if thinking:
        msg["thinking"] = thinking
        
    # Sender attribution
    if role == "user":
        match = msg_regex.search(content)
        if match:
            msg["person_id"] = match.group(1)
    elif role == "tool" and "From: " in content:
        match = file_msg_regex.search(content)
        if match:
            msg["person_id"] = match.group(1)
            msg["role"] = "user"
            
    return msg, False

def parse_transcript(transcript_path: str, cascade_id: str) -> Tuple[Dict[str, Any], int]:
    """Parse a full transcript file and return the session dictionary and error count."""
    messages = []
    skipped_lines = 0
    
    with open(transcript_path, "r") as f:
        for line in f:
            msg, is_error = parse_transcript_line(line)
            if is_error:
                skipped_lines += 1
            elif msg is not None:
                messages.append(msg)
                
    start_time = messages[0]["timestamp"] if messages else "1970-01-01T00:00:00.000Z"
    end_time = messages[-1]["timestamp"] if messages else "1970-01-01T00:00:00.000Z"

    my_session = {
      "cascade_id": cascade_id,
      "title": "Antigravity CLI Session",
      "step_count": len(messages),
      "created_time": start_time,
      "last_modified_time": end_time,
      "messages": messages
    }
    
    return my_session, skipped_lines

def export_session(transcript_path: str, output_path: str, cascade_id: str) -> None:
    """Read transcript, parse, and append to existing export JSON."""
    existing_data = []
    if os.path.exists(output_path):
        try:
            with open(output_path, "r") as f:
                existing_data = json.load(f)
        except Exception as e:
            print(f"Error reading existing export: {e}")
            
    # Remove existing entry for this cascade_id
    existing_data = [conv for conv in existing_data if conv.get("cascade_id") != cascade_id]
    
    my_session, skipped_lines = parse_transcript(transcript_path, cascade_id)
    
    if skipped_lines > 0:
        print(f"WARNING: Skipped {skipped_lines} lines during parsing.")
        
    existing_data.append(my_session)
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(existing_data, f, indent=2)
        
    print(f"Exported {len(my_session['messages'])} messages. Total conversations: {len(existing_data)}")
