def transcribe_audio(audio_bytes: bytes) -> str | None:
    """Распознаёт аудио через Gemini Flash на CheapAI."""
    b64 = base64.b64encode(audio_bytes).decode("utf-8")

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "gemini-3.5-flash",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Распознай речь из этого аудио. Верни только текст, без лишних слов."},
                    {"type": "input_audio", "input_audio": {"data": b64, "format": "ogg"}},
                ],
            }
        ],
        "max_tokens": 500,
    }

    response = requests.post(
        f"{BASE_URL}/chat/completions",
        headers=headers,
        json=payload,
        timeout=30,
    )

    if response.status_code != 200:
        print(f"Ошибка распознавания: {response.status_code} {response.text}")
        return None

    result = response.json()
    return result["choices"][0]["message"]["content"].strip()
