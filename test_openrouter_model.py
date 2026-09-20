from app import create_app
from app.ai.openrouter_client import (
    OpenRouterClient,
    OpenRouterError,
)


app = create_app()


with app.app_context():

    print()
    print("=" * 70)
    print("ANGELIX OPENROUTER MODEL TEST")
    print("=" * 70)

    print()
    print("MODEL:")
    print(app.config["OPENROUTER_MODEL"])

    print()
    print("BASE URL:")
    print(app.config["OPENROUTER_BASE_URL"])

    print()

    client = OpenRouterClient()

    messages = [
        {
            "role": "system",
            "content": (
                "You are a financial analytics assistant "
                "for the Angelix application."
            ),
        },
        {
            "role": "user",
            "content": (
                "Reply with exactly this JSON object "
                "and nothing else: "
                '{"status":"success","message":"Angelix AI is working."}'
            ),
        },
    ]

    try:

        response = client.chat(
            messages=messages,
            temperature=0.1,
            max_tokens=200,
            response_format={
                "type": "json_object"
            },
        )

        print("AI RESPONSE:")
        print(response)

        print()
        print("=" * 70)
        print("OPENROUTER MODEL TEST PASSED")
        print("=" * 70)

    except OpenRouterError as exc:

        print()
        print("=" * 70)
        print("OPENROUTER MODEL TEST FAILED")
        print("=" * 70)

        print()
        print("ERROR:")
        print(str(exc))

        raise