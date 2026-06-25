import json
import pytest
import os
from antigravity_history.cli_parser import parse_transcript_line, export_session

def test_parse_valid_user_input():
    line = json.dumps({
        "source": "USER_EXPLICIT",
        "type": "USER_INPUT",
        "content": "<USER_REQUEST>\nhello\n</USER_REQUEST>",
        "created_at": "2026-06-25T10:00:00Z"
    })
    msg, error_reason = parse_transcript_line(line)
    assert not error_reason
    assert msg["role"] == "user"
    assert msg["content"] == "<USER_REQUEST>\nhello\n</USER_REQUEST>"
    assert msg["timestamp"] == "2026-06-25T10:00:00Z"

def test_parse_thinking_block():
    line = json.dumps({
        "source": "MODEL",
        "type": "PLANNER_RESPONSE",
        "content": "My response",
        "thinking": "My internal reasoning",
        "created_at": "2026-06-25T10:01:00Z"
    })
    msg, error_reason = parse_transcript_line(line)
    assert not error_reason
    assert msg["role"] == "assistant"
    assert msg["content"] == "My response"
    assert msg["thinking"] == "My internal reasoning"

def test_parse_tool_call_without_content():
    line = json.dumps({
        "source": "MODEL",
        "type": "PLANNER_RESPONSE",
        "tool_calls": [{"name": "view_file"}],
        "created_at": "2026-06-25T10:02:00Z"
    })
    msg, error_reason = parse_transcript_line(line)
    assert not error_reason
    assert msg["role"] == "assistant"
    assert "view_file" in msg["content"]

def test_parse_tool_response():
    line = json.dumps({
        "source": "MODEL",
        "type": "VIEW_FILE",
        "content": "File contents",
        "created_at": "2026-06-25T10:03:00Z"
    })
    msg, error_reason = parse_transcript_line(line)
    assert not error_reason
    assert msg["role"] == "tool"
    assert msg["content"] == "File contents"

def test_parse_cli_transcript_tool_result_format():
    # Representative fixture proving that the CLI format (where tool results are raw strings
    # dumped into the 'content' field under source=MODEL, type=GENERIC) is correctly
    # mapped to role=tool with the full output intact. This enforces Two-Parser Coherence.
    line = json.dumps({
        "step_index": 1234,
        "source": "MODEL",
        "type": "GENERIC",
        "status": "DONE",
        "created_at": "2026-06-25T02:04:13Z",
        "content": "Created At: 2026-06-25T02:04:13Z\nCompleted At: 2026-06-25T02:04:13Z\nTask: 1234\nStatus: RUNNING\nLog: /some/path.log\n"
    })
    msg, error_reason = parse_transcript_line(line)
    assert not error_reason
    assert msg["role"] == "tool"
    assert "Log: /some/path.log" in msg["content"]


def test_parse_ephemeral_message_ignored():
    line = json.dumps({
        "source": "SYSTEM",
        "type": "EPHEMERAL_MESSAGE",
        "content": "Some reminder",
        "created_at": "2026-06-25T10:04:00Z"
    })
    msg, error_reason = parse_transcript_line(line)
    assert not error_reason
    assert msg is None

def test_parse_system_message_tool():
    line = json.dumps({
        "source": "SYSTEM",
        "type": "SYSTEM_MESSAGE",
        "content": "Timer fired",
        "created_at": "2026-06-25T10:05:00Z"
    })
    msg, error_reason = parse_transcript_line(line)
    assert not error_reason
    assert msg["role"] == "tool"
    assert msg["content"] == "Timer fired"

def test_parse_invalid_json():
    msg, error_reason = parse_transcript_line("{bad_json: 123")
    assert error_reason
    assert msg is None

def test_parse_person_id_attribution():
    line = json.dumps({
        "source": "MODEL",
        "type": "VIEW_FILE",
        "content": "From: cora-2f1e43dc sent at 2026-06-25T13:45\nTopic: messages\n\nHello!",
        "created_at": "2026-06-25T10:06:00Z"
    })
    msg, error_reason = parse_transcript_line(line)
    assert not error_reason
    assert msg["role"] == "tool"
    assert msg["person_id"] == "cora-2f1e43dc"
    assert "Hello!" in msg["content"]

def test_parse_unknown_source_error_reason():
    line = json.dumps({
        "source": "UNKNOWN_SOURCE",
        "type": "UNKNOWN",
        "content": "Data",
        "created_at": "2026-06-25T10:07:00Z"
    })
    msg, error_reason = parse_transcript_line(line)
    assert error_reason
    assert msg is None

def test_export_session_dedup(tmp_path):
    # Create a dummy transcript file
    transcript_file = tmp_path / "transcript.jsonl"
    line = json.dumps({
        "source": "USER_EXPLICIT",
        "type": "USER_INPUT",
        "content": "test message",
        "created_at": "2026-06-25T10:00:00Z"
    })
    transcript_file.write_text(line + "\n")
    
    output_file = tmp_path / "export.json"
    cascade_id = "test-cascade-uuid-1234"
    
    # First export
    export_session(str(transcript_file), str(output_file), cascade_id)
    
    assert output_file.exists()
    with open(output_file) as f:
        data = json.load(f)
        
    assert len(data) == 1
    assert data[0]["cascade_id"] == cascade_id
    assert len(data[0]["messages"]) == 1
    
    # Second export (should de-dup / replace)
    export_session(str(transcript_file), str(output_file), cascade_id)
    
    with open(output_file) as f:
        data = json.load(f)
        
    # Still 1 conversation, not 2
    assert len(data) == 1
    assert data[0]["cascade_id"] == cascade_id
    assert len(data[0]["messages"]) == 1

def test_export_session_corrupt_existing(tmp_path):
    # Create a dummy transcript file
    transcript_file = tmp_path / "transcript.jsonl"
    line = json.dumps({
        "source": "USER_EXPLICIT",
        "type": "USER_INPUT",
        "content": "test message",
        "created_at": "2026-06-25T10:00:00Z"
    })
    transcript_file.write_text(line + "\n")
    
    output_file = tmp_path / "export.json"
    cascade_id = "test-cascade-uuid-1234"
    
    # Create a corrupt existing export file
    output_file.write_text("this is not valid json, [} corrupt {")
    
    # Export should fail and raise RuntimeError rather than overwriting
    with pytest.raises(RuntimeError, match="Aborting to prevent data loss"):
        export_session(str(transcript_file), str(output_file), cascade_id)
        
    # Verify the corrupt file was NOT overwritten with valid empty/new JSON
    assert output_file.read_text() == "this is not valid json, [} corrupt {"
