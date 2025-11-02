import os
from dotenv import load_dotenv
from anthropic import Anthropic

# Load environment variables from .env file
load_dotenv()

# Initialize the Anthropic client
client = Anthropic(
    api_key=os.getenv('ANTHROPIC_API_KEY')
)

def main():
    """
    Simple example using the Anthropic API
    """
    print("Testing Anthropic API connection...")

    try:
        # Create a message using Claude
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": "Hello! Please respond with a short greeting."}
            ]
        )

        print("\nAPI Response:")
        print(message.content[0].text)
        print("\nAPI key is working correctly!")

    except Exception as e:
        print(f"\nError: {e}")
        print("Please check your API key in the .env file")

if __name__ == "__main__":
    main()
