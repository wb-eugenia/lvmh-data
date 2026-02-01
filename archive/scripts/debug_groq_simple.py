
import os
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Force reload .env
load_dotenv(override=True)

async def main():
    key = os.getenv("GROQ_API_KEY")
    print(f"Key loaded: {key[:10]}...{key[-5:] if key else ''}")
    print(f"Key length: {len(key) if key else 0}")
    
    client = AsyncOpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=key
    )
    
    try:
        completion = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "user", "content": "Hello"}
            ]
        )
        print("Success:", completion.choices[0].message.content)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(main())
