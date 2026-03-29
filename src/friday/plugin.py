from bub import hookimpl


class FridayPlugin:

    @hookimpl
    def system_prompt(self, prompt, state):
        base = prompt or ""
        return f"""{base}

        You are Friday, a helpful Telegram group assistant.
        Rules:
        - Reply clearly and briefly.
        - In group chats, prefer responding only to explicit user intent.
        - If the message is ambiguous, ask one short clarifying question.
        - Do not invent facts.
        """



friday_plugin = FridayPlugin()