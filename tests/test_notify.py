from homework.notify import MAX_LEN, split_message


def test_short_message_is_one_chunk():
    assert split_message("Hello\nworld") == ["Hello\nworld"]


def test_empty_message_gives_no_chunks():
    assert split_message("") == []
    assert split_message("\n\n") == []


def test_long_message_splits_at_line_ends_without_losing_text():
    lines = [f"• line {n}: " + "x" * 50 for n in range(300)]
    text = "\n".join(lines)
    chunks = split_message(text)
    assert len(chunks) > 1
    assert all(len(c) <= MAX_LEN for c in chunks)
    # every chunk boundary falls on a line boundary, so rejoining gives the original
    assert "\n".join(chunks) == text


def test_single_overlong_line_is_hard_split():
    text = "y" * (MAX_LEN * 2 + 10)
    chunks = split_message(text)
    assert [len(c) for c in chunks] == [MAX_LEN, MAX_LEN, 10]
    assert "".join(chunks) == text


def test_limit_counts_emoji_as_two_units():
    # "⚠" is 1 UTF-16 unit, "📚" is 2: Telegram counts UTF-16 units.
    text = "📚" * 3
    chunks = split_message(text, limit=4)
    assert chunks == ["📚📚", "📚"]


def test_custom_limit():
    chunks = split_message("aaa\nbbb\nccc", limit=8)
    assert chunks == ["aaa\nbbb", "ccc"]
