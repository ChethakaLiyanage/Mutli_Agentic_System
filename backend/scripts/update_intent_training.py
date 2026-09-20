"""Update intent training data to include active and hypothetical accident statements."""

import csv
from collections import Counter
from pathlib import Path

from backend.app.nlp.intent_classifier import (
    DEFAULT_CLEAN_EVALUATION_PATH,
    DEFAULT_DATASET_PATH,
    DEFAULT_NOISY_EVALUATION_PATH,
    INTENT_LABELS,
    train_intent_classifier,
)


def update_and_retrain():
    # Load evaluation sets to ensure zero overlap
    def load_texts(path: Path) -> set[str]:
        with path.open(encoding="utf-8", newline="") as f:
            return {row["text"].casefold().strip() for row in csv.DictReader(f)}

    clean_eval = load_texts(DEFAULT_CLEAN_EVALUATION_PATH)
    noisy_eval = load_texts(DEFAULT_NOISY_EVALUATION_PATH)
    forbidden_texts = clean_eval | noisy_eval | {
        "i wana mak a clam",
        "does my polcy covr flod dmg",
        "wat documnts do i ned for theft",
        "chec my clam stats",
        "tell me abt my polcy",
        "good mornin does my polcy cover flood",
        "helo i need to submit a claim",
        "ih",
        "hii",
        "helo",
        "god mornin",
        "i ned to file cliam",
        "does my polciy covr flod dmg",
    }

    # Load existing training rows
    rows_by_label: dict[str, list[str]] = {label: [] for label in INTENT_LABELS}
    with DEFAULT_DATASET_PATH.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            text = r["text"].strip()
            label = r["label"].strip()
            if text.casefold() not in forbidden_texts and text not in rows_by_label[label]:
                rows_by_label[label].append(text)

    # Active accident statements to include in claim_submission
    active_accident_statements = [
        "i just had accident",
        "had an accident just now",
        "im accidented just now",
        "i got accident few mins ago",
        "someone hit my car just now",
        "my car got hit today",
        "i crashed my car what should i do",
        "just got into accident",
        "accident happened few minutes ago",
        "I just had an accident, what should I do",
        "my vehicle was damaged just now",
        "I crashed my vehicle earlier today",
    ]

    # Hypothetical accident statements to include in general_information
    hypothetical_accident_statements = [
        "What should I do if I have an accident",
        "What should I do in case of an accident",
        "If I get into an accident what should I do",
        "What is the procedure if my car gets damaged",
        "What should a driver do if an accident occurs",
        "How do I proceed if I have a motor accident",
        "What steps should be taken if a collision happens",
        "If someone damages my car what should I generally do",
        "What is the protocol if an accident takes place",
        "Can you tell me what to do if an accident happens",
    ]

    # Prepend active statements to claim_submission
    existing_cs = [t for t in rows_by_label["claim_submission"] if t.casefold() not in {s.casefold() for s in active_accident_statements}]
    rows_by_label["claim_submission"] = active_accident_statements + existing_cs

    # Prepend hypothetical statements to general_information
    existing_gi = [t for t in rows_by_label["general_information"] if t.casefold() not in {s.casefold() for s in hypothetical_accident_statements}]
    rows_by_label["general_information"] = hypothetical_accident_statements + existing_gi

    # Ensure other classes have clean non-overlapping samples up to 50
    replacements = {
        "thanks": ["thx so much for your support", "appreciate the guidance", "thank you very much for helping"],
        "goodbye": ["c u later", "bye for today", "farewell have a good day"],
        "acknowledgement": ["fine with me", "i understand that completely", "sounds very good"],
    }
    for label, extra_samples in replacements.items():
        for s in extra_samples:
            if s.casefold() not in forbidden_texts and s not in rows_by_label[label]:
                rows_by_label[label].append(s)

    # Trim or ensure each class has exactly 50 samples
    target_count = 50
    final_rows: list[dict[str, str]] = []
    for label in INTENT_LABELS:
        samples = rows_by_label[label][:target_count]
        if len(samples) < target_count:
            raise ValueError(f"Label {label} has only {len(samples)} samples, expected {target_count}")
        for s in samples:
            final_rows.append({"text": s, "label": label})

    print("Updated class distribution:", Counter(r["label"] for r in final_rows))
    print("Total rows:", len(final_rows))

    # Save to intent_training.csv
    with DEFAULT_DATASET_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "label"])
        writer.writeheader()
        writer.writerows(final_rows)

    print("Successfully wrote updated intent_training.csv")


if __name__ == "__main__":
    update_and_retrain()
