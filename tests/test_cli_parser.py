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
    msg, is_error = parse_transcript_line(line)
    assert not is_error
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
    msg, is_error = parse_transcript_line(line)
    assert not is_error
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
    msg, is_error = parse_transcript_line(line)
    assert not is_error
    assert msg["role"] == "assistant"
    assert "view_file" in msg["content"]

def test_parse_tool_response():
    line = json.dumps({
        "source": "MODEL",
        "type": "VIEW_FILE",
        "content": "File contents",
        "created_at": "2026-06-25T10:03:00Z"
    })
    msg, is_error = parse_transcript_line(line)
    assert not is_error
    assert msg["role"] == "tool"
    assert msg["content"] == "File contents"

def test_parse_ephemeral_message_ignored():
    line = json.dumps({
        "source": "SYSTEM",
        "type": "EPHEMERAL_MESSAGE",
        "content": "Some reminder",
        "created_at": "2026-06-25T10:04:00Z"
    })
    msg, is_error = parse_transcript_line(line)
    assert not is_error
    assert msg is None

def test_parse_system_message_tool():
    line = json.dumps({
        "source": "SYSTEM",
        "type": "SYSTEM_MESSAGE",
        "content": "Timer fired",
        "created_at": "2026-06-25T10:05:00Z"
    })
    msg, is_error = parse_transcript_line(line)
    assert not is_error
    assert msg["role"] == "tool"
    assert msg["content"] == "Timer fired"

def test_parse_invalid_json():
    msg, is_error = parse_transcript_line("{bad_json: 123")
    assert is_error
    assert msg is None

def test_parse_person_id_attribution():
    line = json.dumps({
        "source": "MODEL",
        "type": "VIEW_FILE",
        "content": "From: cora-2f1e43dc sent at 2026-06-25T13:45\nTopic: messages\n\nHello!",
        "created_at": "2026-06-25T10:06:00Z"
    })
    msg, is_error = parse_transcript_line(line)
    assert not is_error
    assert msg["role"] == "tool"
    assert msg["person_id"] == "cora-2f1e43dc"
    assert "Hello!" in msg["content"]

def test_parse_unknown_source_is_error():
    line = json.dumps({
        "source": "UNKNOWN_SOURCE",
        "type": "UNKNOWN",
        "content": "Data",
        "created_at": "2026-06-25T10:07:00Z"
    })
    msg, is_error = parse_transcript_line(line)
    assert is_error
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
