from utils.deepseek_tokenizer import count_prompt_tokens, count_text_tokens, get_tokenizer


def test_tokenizer_loads_from_module_directory() -> None:
    assert get_tokenizer() is get_tokenizer()
    assert count_text_tokens("Hello!") > 0


def test_prompt_estimate_includes_all_input() -> None:
    prompt_only = count_prompt_tokens("Сделай вывод")
    full = count_prompt_tokens(
        "Сделай вывод",
        instructions="Отвечай кратко",
        input_data=["Первый источник", "Второй источник"],
    )
    assert full > prompt_only
