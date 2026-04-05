from friday.message_context import parse_message_context


def test_parse_telegram_context_builds_session_and_actor_keys():
    raw = (
        '{"message":"继续实现 Friday 记忆","message_id":42,"type":"text",'
        '"username":"Muzy_ch","full_name":"Muzych","sender_id":"6732122782",'
        '"sender_is_bot":false,"date":1774754554.0}'
    )

    ctx = parse_message_context(
        channel="telegram",
        session_id="telegram:-1002175041416",
        chat_id="-1002175041416",
        raw_content=raw,
    )

    assert ctx.session_key == "telegram:-1002175041416"
    assert ctx.actor_key == "telegram:6732122782"
    assert ctx.display_name == "Muzych"


def test_parse_plain_content_keeps_session_and_text():
    ctx = parse_message_context(
        channel="cli",
        session_id="cli:default",
        chat_id="default",
        raw_content="hello friday",
    )

    assert ctx.session_key == "cli:default"
    assert ctx.actor_key is None
    assert ctx.message_text == "hello friday"
