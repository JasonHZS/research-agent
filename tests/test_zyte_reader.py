"""
Test script for Zyte API Reader Tool

Usage:
    # Article extraction
    python tests/test_zyte_reader.py              # Test article extraction
    python tests/test_zyte_reader.py --raw        # Show raw API response
    python tests/test_zyte_reader.py <url>        # Custom URL

    # Article list extraction
    python tests/test_zyte_reader.py --list                    # Test article list
    python tests/test_zyte_reader.py --list --raw              # Show raw list response
    python tests/test_zyte_reader.py --list <url>              # Custom list URL
"""

import os
import sys

from dotenv import load_dotenv

sys.path.append(os.getcwd())

from src.tools.zyte_reader import (
    fetch_article_content,
    fetch_article_list,
    get_zyte_article_list_tool,
    get_zyte_reader_tool,
)


def test_zyte_reader(url: str = "https://blog.rybarix.com/2025/12/16/going-fast.html"):
    """Test the Zyte Reader tool."""
    load_dotenv()

    print(f"Fetching: {url}\n")

    result = get_zyte_reader_tool.invoke({"url": url})

    if result.startswith("Error"):
        print(f"❌ {result}")
    else:
        print("✅ Success\n")
        print(result)

    return result


def test_zyte_reader_raw(url: str = "https://blog.rybarix.com/2025/12/16/going-fast.html"):
    """Test raw API response."""
    load_dotenv()

    print(f"Fetching raw: {url}\n")

    try:
        result = fetch_article_content(url)
        if "article" in result:
            article = result["article"]
            print(f"Headline: {article.get('headline', 'N/A')}")
            print(f"Authors: {article.get('authors', 'N/A')}")
            print(f"Date: {article.get('datePublished', 'N/A')}")
            if body := article.get("articleBody"):
                print(f"\nBody preview:\n{body[:500]}...")
        else:
            print(f"No article found: {result}")
    except Exception as e:
        print(f"❌ {e}")


def test_article_list(url: str = "https://blog.langchain.com/"):
    """Test the Zyte Article List tool."""
    load_dotenv()

    print(f"Fetching article list: {url}\n")

    result = get_zyte_article_list_tool.invoke({"url": url})

    if result.startswith("Error"):
        print(f"❌ {result}")
    else:
        print("✅ Success\n")
        print(result)

    return result


def test_article_list_raw(url: str = "https://blog.langchain.com/"):
    """Test raw article list API response."""
    load_dotenv()

    print(f"Fetching raw article list: {url}\n")

    try:
        result = fetch_article_list(url)
        
        # Debug: show response structure
        print(f"Response keys: {list(result.keys())}")
        
        if "articleList" in result:
            article_list_data = result["articleList"]
            
            # Debug: show articleList structure
            print(f"articleList type: {type(article_list_data).__name__}")
            
            # Handle nested structure: articleList might contain an "articles" key
            if isinstance(article_list_data, dict):
                print(f"articleList keys: {list(article_list_data.keys())}")
                articles = article_list_data.get("articles", [])
            else:
                articles = article_list_data
            
            print(f"Found {len(articles)} articles:\n")
            
            # Get first 10 articles
            articles_to_show = articles[:10] if isinstance(articles, list) else list(articles)[:10]
            
            for i, article in enumerate(articles_to_show, 1):
                # Handle both dict and other types
                if isinstance(article, dict):
                    print(f"{i}. {article.get('headline', 'Untitled')}")
                    print(f"   URL: {article.get('url', 'N/A')}")
                    print(f"   Published: {article.get('datePublished', 'N/A')}")
                    print(f"   Language: {article.get('inLanguage', 'N/A')}")
                    if body := article.get("articleBody"):
                        preview = body[:100] + "..." if len(body) > 100 else body
                        print(f"   Preview: {preview}")
                else:
                    # Debug: show actual type and value
                    print(f"{i}. [Type: {type(article).__name__}] {article}")
                print()

            if len(articles) > 10:
                print(f"... and {len(articles) - 10} more articles")
        else:
            print(f"No article list found. Keys in response: {list(result.keys())}")
            print(f"Full response: {result}")
    except Exception as e:
        import traceback
        print(f"❌ {e}")
        traceback.print_exc()


if __name__ == "__main__":
    args = sys.argv[1:]

    # Check for --list flag
    is_list_mode = "--list" in args
    if is_list_mode:
        args.remove("--list")

    # Check for --raw flag
    is_raw_mode = "--raw" in args
    if is_raw_mode:
        args.remove("--raw")

    # Get custom URL if provided
    custom_url = args[0] if args else None

    if is_list_mode:
        # Article list mode
        if is_raw_mode:
            if custom_url:
                test_article_list_raw(custom_url)
            else:
                test_article_list_raw()
        else:
            if custom_url:
                test_article_list(custom_url)
            else:
                test_article_list()
    else:
        # Article extraction mode
        if is_raw_mode:
            if custom_url:
                test_zyte_reader_raw(custom_url)
            else:
                test_zyte_reader_raw()
        else:
            if custom_url:
                test_zyte_reader(custom_url)
            else:
                test_zyte_reader()
