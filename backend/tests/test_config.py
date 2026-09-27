"""Tests for configuration loading and path resolution."""



def test_settings_defaults():
    from app.config import settings

    assert settings.APP_NAME
    assert settings.CHUNK_SIZE == 500
    assert settings.CHUNK_OVERLAP == 50
    assert settings.TOP_K_RETRIEVAL == 5
    assert settings.MAX_FILE_SIZE_MB == 50


def test_resolve_path_is_absolute():
    from app.config import resolve_path

    resolved = resolve_path("./data/chroma")
    assert resolved.startswith("/")
    assert resolved.endswith("data/chroma")


def test_resolve_path_keeps_absolute_paths():
    from app.config import resolve_path

    assert resolve_path("/tmp/chroma") == "/tmp/chroma"


def test_async_database_url_uses_async_driver():
    from app.config import settings

    url = settings.async_database_url
    assert url.startswith("sqlite+aiosqlite:///")
    # The path portion must be absolute so CWD does not matter.
    assert ":///" in url
    path_part = url.split(":///", 1)[1]
    assert path_part.startswith("/")


def test_ensure_directories_creates_paths():
    from pathlib import Path

    from app.config import settings

    settings.ensure_directories()
    assert Path(settings.chroma_path).is_dir()
    assert Path(settings.upload_path).is_dir()


# -- OpenAI client arguments -----------------------------------------------


def test_client_kwargs_omit_base_url_when_unset():
    """An explicit `base_url=""` breaks every request; it must be absent.

    The SDK reads an empty base_url as a real origin and fails with an opaque
    URL error, so "not configured" has to be expressed by not passing the
    argument at all.
    """
    from app.config import Settings

    kwargs = Settings(OPENAI_API_KEY="sk-real-key", OPENAI_BASE_URL="").openai_client_kwargs

    assert kwargs == {"api_key": "sk-real-key"}
    assert "base_url" not in kwargs


def test_client_kwargs_pass_a_configured_base_url():
    from app.config import Settings

    kwargs = Settings(
        OPENAI_API_KEY="sk-real-key", OPENAI_BASE_URL="https://gateway.example/v1"
    ).openai_client_kwargs

    assert kwargs["api_key"] == "sk-real-key"
    assert kwargs["base_url"] == "https://gateway.example/v1"


def test_client_kwargs_strip_a_trailing_slash_from_base_url():
    # A trailing slash yields ".../v1//chat/completions" on some gateways.
    from app.config import Settings

    kwargs = Settings(OPENAI_BASE_URL="https://gateway.example/v1/").openai_client_kwargs

    assert kwargs["base_url"] == "https://gateway.example/v1"


def test_client_kwargs_treat_whitespace_base_url_as_unset():
    from app.config import Settings

    kwargs = Settings(OPENAI_BASE_URL="   ").openai_client_kwargs

    assert "base_url" not in kwargs


# -- Placeholder keys ------------------------------------------------------


def test_usable_api_key_rejects_an_empty_key():
    from app.config import usable_api_key

    assert usable_api_key("") is False
    assert usable_api_key(None) is False
    assert usable_api_key("   ") is False


def test_usable_api_key_rejects_the_copied_placeholder():
    # A freshly copied config must behave as if no key were set, so that it
    # produces no auth errors and makes no billed calls.
    from app.config import usable_api_key

    assert usable_api_key("sk-your-key-here") is False
    assert usable_api_key("gsk-your-key-here") is False
    assert usable_api_key("YOUR-KEY") is False


def test_usable_api_key_accepts_a_real_looking_key():
    from app.config import usable_api_key

    assert usable_api_key("sk-proj-abc123") is True
    assert usable_api_key("gsk_3cF7A1JfNjiyERB4J2gxWGdyb3FYM7vA") is True


# -- Chat endpoint resolution ----------------------------------------------


def test_llm_endpoint_is_none_without_any_key():
    from app.config import Settings

    assert Settings().llm_endpoint is None


def test_llm_endpoint_uses_groq_with_its_own_default_url():
    from app.config import Settings

    endpoint = Settings(GROQ_API_KEY="gsk-abc123").llm_endpoint

    assert endpoint is not None
    provider, kwargs = endpoint
    assert provider == "groq"
    assert kwargs["api_key"] == "gsk-abc123"
    # Baked in, so configuring a Groq key does not also require a URL.
    assert kwargs["base_url"] == "https://api.groq.com/openai/v1"


def test_llm_endpoint_prefers_groq_over_openai():
    from app.config import Settings

    endpoint = Settings(
        GROQ_API_KEY="gsk-abc123", OPENAI_API_KEY="sk-abc123"
    ).llm_endpoint

    assert endpoint[0] == "groq"


def test_llm_endpoint_falls_back_to_openai():
    from app.config import Settings

    endpoint = Settings(OPENAI_API_KEY="sk-abc123").llm_endpoint

    assert endpoint[0] == "openai"
    assert endpoint[1]["api_key"] == "sk-abc123"


def test_llm_endpoint_ignores_a_placeholder_groq_key():
    from app.config import Settings

    assert Settings(GROQ_API_KEY="gsk-your-key-here").llm_endpoint is None


def test_groq_key_never_leaks_into_the_embedding_client():
    """Groq serves chat completions, not embeddings.

    Sharing one key across both would be a mistake waiting to happen: adding
    a Groq key must not make the embedding client call an inference endpoint,
    which would also change the vector width and invalidate the index.
    """
    from app.config import Settings

    settings = Settings(GROQ_API_KEY="gsk-abc123", OPENAI_API_KEY="")

    assert "gsk-abc123" not in str(settings.openai_client_kwargs)
