from types import SimpleNamespace

from async_panes.async_panes_utils import build_transcript, format_transcript


class DummyMemory:
    def __init__(self, items):
        self._items = items

    def get_all(self):
        return list(self._items)


class BrokenMemory:
    """get_all() raises — should be treated as empty transcript."""
    def get_all(self):
        raise RuntimeError("storage unavailable")


class BrokenAttrItem:
    """Object whose .role property raises — defensive except path."""
    @property
    def role(self):
        raise RuntimeError("broken")

    @property
    def content(self):
        raise RuntimeError("broken")


def test_build_transcript_basic_roles():
    mem = DummyMemory(
        [
            SimpleNamespace(role="user", content="Hello"),
            SimpleNamespace(role="assistant", content="Hi there"),
            {"role": "human", "content": "Where are we?"},
            {"role": "tool", "content": "irrelevant tool output"},
        ]
    )
    t = build_transcript(mem)
    # Normalizes roles to user/agent
    assert t[0]["role"] == "user"
    assert t[1]["role"] == "agent"
    assert t[2]["role"] == "user"
    assert t[3]["role"] == "agent"


def test_build_transcript_appends_latest_exchange():
    mem = DummyMemory([SimpleNamespace(role="user", content="A")])
    t = build_transcript(mem, last_user_msg="B", last_agent_msg="C")
    assert t[-2:] == [
        {"role": "user", "content": "B"},
        {"role": "agent", "content": "C"},
    ]


def test_format_transcript_prefixes():
    transcript = [
        {"role": "user", "content": "Ask"},
        {"role": "agent", "content": "Reply"},
    ]
    s = format_transcript(transcript)
    assert s.splitlines()[0].startswith("User:")
    assert s.splitlines()[1].startswith("Keeper:")


def test_format_transcript_last_k():
    transcript = [
        {"role": "user", "content": "A"},
        {"role": "agent", "content": "B"},
        {"role": "user", "content": "C"},
        {"role": "agent", "content": "D"},
    ]
    s = format_transcript(transcript, last_k=2)
    lines = s.splitlines()
    assert len(lines) == 2
    assert "C" in lines[0]
    assert "D" in lines[1]


def test_build_transcript_dedup_last_user_msg_already_in_memory():
    """last_user_msg already present in the most recent memory turn → must not be appended again."""
    mem = DummyMemory(
        [
            SimpleNamespace(role="user", content="Hello"),
            SimpleNamespace(role="assistant", content="World"),
        ]
    )
    t = build_transcript(mem, last_user_msg="Hello", last_agent_msg="World")
    user_msgs = [m for m in t if m["role"] == "user"]
    # "Hello" must appear exactly once
    assert sum(1 for m in user_msgs if m["content"] == "Hello") == 1


def test_build_transcript_max_len_truncation():
    items = [SimpleNamespace(role="user", content=str(i)) for i in range(50)]
    mem = DummyMemory(items)
    t = build_transcript(mem, max_len=10)
    assert len(t) == 10
    # Should keep the most recent messages
    assert t[-1]["content"] == "49"


def test_build_transcript_broken_memory_returns_empty():
    """memory.get_all() raises → transcript is empty, no exception propagated."""
    t = build_transcript(BrokenMemory())
    assert t == []


def test_build_transcript_broken_attr_item_falls_back_to_dict_path():
    """Item whose .role/.content properties raise → falls back to dict check, then skipped."""
    mem = DummyMemory([BrokenAttrItem()])
    t = build_transcript(mem)
    # The broken item has no dict fallback either, so it should be silently skipped
    assert t == []


def test_build_transcript_empty_content_skipped():
    """Items with falsy content are silently dropped."""
    mem = DummyMemory([
        SimpleNamespace(role="user", content=""),
        SimpleNamespace(role="user", content=None),
        SimpleNamespace(role="user", content="real"),
    ])
    t = build_transcript(mem)
    assert len(t) == 1
    assert t[0]["content"] == "real"
