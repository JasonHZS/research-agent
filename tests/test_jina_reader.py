"""
Test script for Jina AI Reader Tool

This script tests the Jina AI Reader tool to fetch URL content as markdown.
"""

import os
import sys

from dotenv import load_dotenv

# Ensure the project root is in python path
sys.path.append(os.getcwd())

from src.tools.jina_reader import fetch_url_as_markdown, get_jina_reader_tool


def test_jina_reader():
    """Test the Jina AI Reader tool with a sample URL."""
    # Load environment variables
    load_dotenv()

    print("=" * 60)
    print("Testing Jina AI Reader Tool")
    print("=" * 60)

    # Test URL - using a simple example
    test_url = "https://apple.github.io/ml-sharp/"

    print(f"\n📎 Fetching content from: {test_url}")
    print("-" * 60)

    # Test using the LangChain tool
    result = get_jina_reader_tool.invoke({"url": test_url})

    if result.startswith("Error"):
        print(f"\n❌ {result}")
        print("\nTroubleshooting:")
        print("1. Set JINA_API_KEY in your .env file")
        print("2. Check your network connection")
        print("3. Verify the target URL is accessible")
    else:
        print("\n✅ Successfully fetched content!")
        print(f"\n📄 Result (first 2000 chars):\n")
        print(result[:2000])
        if len(result) > 2000:
            print(f"\n... (truncated, total length: {len(result)} chars)")

    print("\n" + "-" * 60)


def test_jina_reader_with_custom_url(url: str):
    """Test the Jina AI Reader tool with a custom URL."""
    load_dotenv()

    print("=" * 60)
    print("Testing Jina AI Reader Tool - Custom URL")
    print("=" * 60)

    print(f"\n📎 Fetching content from: {url}")
    print("-" * 60)

    # Test using the LangChain tool
    result = get_jina_reader_tool.invoke({"url": url})

    if result.startswith("Error"):
        print(f"\n❌ {result}")
    else:
        print("\n✅ Successfully fetched content!")
        print(f"\n📄 Result:\n")
        print(result)

    print("\n" + "-" * 60)
    return result


if __name__ == "__main__":
    # If a URL is provided as command line argument, use it
    if len(sys.argv) > 1:
        custom_url = sys.argv[1]
        test_jina_reader_with_custom_url(custom_url)
    else:
        test_jina_reader()
