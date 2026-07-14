from unittest.mock import MagicMock, patch

from llm_client import call_llm


def test_call_llm_returns_response_text(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    fake_message = MagicMock()
    fake_message.content = '{"results": []}'
    fake_choice = MagicMock()
    fake_choice.message = fake_message
    fake_response = MagicMock()
    fake_response.choices = [fake_choice]

    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = fake_response

    with patch("llm_client.OpenAI", return_value=fake_client) as mock_openai:
        result = call_llm("some prompt")

    mock_openai.assert_called_once_with(api_key="test-key")
    fake_client.chat.completions.create.assert_called_once()
    _, kwargs = fake_client.chat.completions.create.call_args
    assert kwargs["messages"][0]["content"] == "some prompt"
    assert result == '{"results": []}'
