"""
Week 6 - One-command setup for the NLP dependencies.

pip installs the libraries, but spaCy, NLTK and Hugging Face each need their
model/corpus files downloaded separately. This script does all three.

Usage (from the project root):

    python -m backend.nlp.setup_nlp
    python -m backend.nlp.setup_nlp --skip-model   # skip the 265 MB download
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from .config import EMBEDDING_MODEL_NAME, QA_MODEL_NAME, RETRIEVAL_MODEL_NAME, SPACY_MODEL

NLTK_PACKAGES = ["stopwords", "punkt", "punkt_tab", "wordnet", "omw-1.4"]


def setup_spacy() -> bool:
    print(f"[1/3] spaCy model '{SPACY_MODEL}'")
    try:
        import spacy

        spacy.load(SPACY_MODEL)
        print("      already installed")
        return True
    except OSError:
        print("      downloading (~12 MB) ...")
        result = subprocess.run(
            [sys.executable, "-m", "spacy", "download", SPACY_MODEL]
        )
        if result.returncode == 0:
            print("      done")
            return True
        print("      FAILED. Install manually with:")
        print(f"        python -m spacy download {SPACY_MODEL}")
        return False
    except ImportError:
        print("      spaCy is not installed. Run: pip install -r requirements.txt")
        return False


def setup_nltk() -> bool:
    print("\n[2/3] NLTK corpora")
    try:
        import nltk
    except ImportError:
        print("      NLTK is not installed. Run: pip install -r requirements.txt")
        return False

    ok = True
    for package in NLTK_PACKAGES:
        downloaded = nltk.download(package, quiet=True)
        print(f"      {package:<12} {'ok' if downloaded else 'FAILED'}")
        ok = ok and downloaded
    return ok


def setup_transformer(skip: bool = False) -> bool:
    print("\n[3/3] Hugging Face models")
    if skip:
        print("      skipped (--skip-model)")
        return True

    try:
        from transformers import AutoModel, AutoModelForQuestionAnswering, AutoTokenizer
    except ImportError:
        print("      transformers/torch not installed.")
        print("      Run: pip install -r requirements.txt")
        return False

    ok = True
    for purpose, name, loader in [
        ("intent classification", EMBEDDING_MODEL_NAME, AutoModel),
        ("lesson retrieval", RETRIEVAL_MODEL_NAME, AutoModel),
        ("answer extraction", QA_MODEL_NAME, AutoModelForQuestionAnswering),
    ]:
        print(f"      {purpose}: {name}")
        print("        downloading (~265 MB, cached after the first run) ...")
        try:
            AutoTokenizer.from_pretrained(name)
            loader.from_pretrained(name)
            print("        done")
        except Exception as exc:  # noqa: BLE001 - report any download failure
            print(f"        FAILED: {exc}")
            print("        This step needs internet access on the first run.")
            ok = False
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Week 6 NLP setup")
    parser.add_argument(
        "--skip-model",
        action="store_true",
        help="do not download the DistilBERT weights",
    )
    args = parser.parse_args()

    print("EduQuest - Week 6 NLP setup")
    print("=" * 50)

    results = [
        setup_spacy(),
        setup_nltk(),
        setup_transformer(skip=args.skip_model),
    ]

    print("\n" + "=" * 50)
    if all(results):
        print("Setup complete. Next:")
        print("  python -m backend.nlp.build_dataset")
        print("  python -m backend.nlp.validate")
    else:
        print("Some steps failed - see the messages above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
