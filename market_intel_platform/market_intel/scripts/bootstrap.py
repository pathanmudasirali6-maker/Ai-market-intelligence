#!/usr/bin/env python
"""
Bootstrap script — downloads required NLP corpora on first run.
Called automatically by the start command before uvicorn/gunicorn.
"""
import sys
import subprocess


def download_corpora():
    print("Checking/downloading NLP corpora...")
    try:
        import nltk
        # Only download what TextBlob's PatternAnalyzer needs (punkt for sentence tokenization)
        # We don't use noun_phrases so brown/conll2000 not needed
        for corpus in ["punkt", "punkt_tab"]:
            try:
                nltk.download(corpus, quiet=True)
            except Exception as e:
                print(f"  Warning: could not download {corpus}: {e}")
        print("NLP corpora ready.")
    except ImportError:
        print("NLTK not installed, skipping corpus download.")


if __name__ == "__main__":
    download_corpora()
