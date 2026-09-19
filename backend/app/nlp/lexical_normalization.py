"""Conservative corpus-fitted lexical normalization for Agent 1."""

from __future__ import annotations

import re
from collections import Counter
from functools import lru_cache
from typing import Iterable

from sklearn.base import BaseEstimator, TransformerMixin

from backend.app.nlp.preprocessing import preprocess_text


GREETING_TERMS = frozenset(
    {
        "afternoon",
        "evening",
        "greetings",
        "hello",
        "hey",
        "hi",
        "morning",
    }
)

GREETING_PHRASES = (
    "hi",
    "hello",
    "hey",
    "greetings",
    "good morning",
    "good afternoon",
    "good evening",
    "hello there",
    "hi there",
)

THANKS_PHRASES = (
    "thanks",
    "thank you",
    "thank you very much",
    "appreciate it",
    "many thanks",
    "thanks a lot",
    "thank you so much",
    "cheers",
)

GOODBYE_PHRASES = (
    "bye",
    "goodbye",
    "good bye",
    "see you",
    "talk later",
    "take care",
    "bye for now",
    "see you later",
)

ACKNOWLEDGEMENT_PHRASES = (
    "ok",
    "okay",
    "got it",
    "alright",
    "understood",
    "noted",
    "sure",
    "sounds good",
    "i understand",
    "all right",
)

INSURANCE_TERMS = frozenset(
    {
        "accident",
        "approve",
        "approved",
        "break",
        "car",
        "claim",
        "collision",
        "comprehensive",
        "cover",
        "coverage",
        "damage",
        "documents",
        "excess",
        "file",
        "flood",
        "forms",
        "information",
        "insurance",
        "insured",
        "motor",
        "papers",
        "policy",
        "premium",
        "report",
        "required",
        "status",
        "submit",
        "theft",
        "vehicle",
        "windscreen",
    }
)

CONVERSATIONAL_TERMS = frozenset(
    {
        "about",
        "acknowledge",
        "alright",
        "am",
        "appreciate",
        "are",
        "bye",
        "can",
        "care",
        "check",
        "cheers",
        "could",
        "do",
        "does",
        "explain",
        "for",
        "good",
        "goodbye",
        "got",
        "have",
        "help",
        "how",
        "is",
        "later",
        "may",
        "me",
        "much",
        "my",
        "need",
        "noted",
        "ok",
        "okay",
        "please",
        "see",
        "sounds",
        "sure",
        "tell",
        "thank",
        "thanks",
        "there",
        "understand",
        "understood",
        "want",
        "what",
        "will",
        "would",
        "you",
    }
)

CONTROLLED_TERMS = GREETING_TERMS | INSURANCE_TERMS | CONVERSATIONAL_TERMS

_PROTECTED_VALUE = re.compile(
    r"https?://[^\s]+|www\.[^\s]+|"
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|"
    r"\b(?:LKR|USD)\b(?=\s+\d)|"
    r"(?<!\w)(?=[A-Za-z0-9_./:-]*\d)[A-Za-z0-9][A-Za-z0-9_./:-]*"
    r"[A-Za-z0-9](?!\w)",
    flags=re.IGNORECASE,
)
_PLACEHOLDER = re.compile(r"zzprotected(?P<index>\d+)zz")
_ALPHABETIC_WORD = re.compile(r"^[a-z]+$")


@lru_cache(maxsize=32_768)
def damerau_levenshtein_distance(left: str, right: str) -> int:
    """Return edit distance including one-step adjacent transpositions."""

    rows = len(left) + 1
    columns = len(right) + 1
    distance = [[0] * columns for _ in range(rows)]
    for row in range(rows):
        distance[row][0] = row
    for column in range(columns):
        distance[0][column] = column

    for row in range(1, rows):
        for column in range(1, columns):
            substitution_cost = left[row - 1] != right[column - 1]
            distance[row][column] = min(
                distance[row - 1][column] + 1,
                distance[row][column - 1] + 1,
                distance[row - 1][column - 1] + substitution_cost,
            )
            if (
                row > 1
                and column > 1
                and left[row - 1] == right[column - 2]
                and left[row - 2] == right[column - 1]
            ):
                distance[row][column] = min(
                    distance[row][column],
                    distance[row - 2][column - 2] + 1,
                )
    return distance[-1][-1]


def _maximum_edit_distance(token: str) -> int:
    if len(token) <= 3:
        return 0
    if len(token) <= 7:
        return 1
    return 2


def _mask_protected_values(text: str) -> tuple[str, list[str]]:
    protected: list[str] = []

    def replace(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        return f" zzprotected{len(protected) - 1}zz "

    return _PROTECTED_VALUE.sub(replace, text), protected


class ControlledTextNormalizer(BaseEstimator, TransformerMixin):
    """Fit a controlled vocabulary and conservatively repair noisy tokens.

    The transformer is the first persisted sklearn pipeline step. Vocabulary
    state therefore travels with the vectorizers and classifier instead of
    being rebuilt independently during runtime inference.
    """

    def __init__(self, min_corpus_frequency: int = 2) -> None:
        self.min_corpus_frequency = min_corpus_frequency

    def fit(
        self,
        texts: Iterable[str],
        _labels: object = None,
    ) -> "ControlledTextNormalizer":
        counts: Counter[str] = Counter()
        for text in texts:
            masked, _ = _mask_protected_values(text)
            counts.update(
                token
                for token in preprocess_text(masked).split()
                if _ALPHABETIC_WORD.fullmatch(token)
                and not token.startswith("zzprotected")
            )

        vocabulary = set(CONTROLLED_TERMS)
        for token, count in counts.items():
            if count < self.min_corpus_frequency:
                continue
            if self._is_variant_of_controlled_term(token):
                continue
            vocabulary.add(token)

        self.vocabulary_ = frozenset(vocabulary)
        self.frequencies_ = {
            token: counts.get(token, 0) for token in self.vocabulary_
        }
        return self

    def transform(self, texts: Iterable[str]) -> list[str]:
        if not hasattr(self, "vocabulary_"):
            raise RuntimeError("ControlledTextNormalizer must be fitted first")
        return [self.normalize(text) for text in texts]

    def normalize(self, text: str) -> str:
        if not isinstance(text, str):
            raise TypeError("text must be a string")

        masked, protected = _mask_protected_values(text)
        cleaned = preprocess_text(masked)
        normalized_tokens: list[str] = []
        for token in cleaned.split():
            placeholder = _PLACEHOLDER.fullmatch(token)
            if placeholder is not None:
                normalized_tokens.append(protected[int(placeholder.group("index"))])
                continue
            normalized_tokens.append(self._normalize_token(token))
        return " ".join(normalized_tokens)

    def _normalize_token(self, token: str) -> str:
        if token in self.vocabulary_ or not _ALPHABETIC_WORD.fullmatch(token):
            return token
        if len(token) < 2:
            return token

        maximum_distance = _maximum_edit_distance(token)
        candidates: list[tuple[int, int, int, str]] = []
        for candidate in self.vocabulary_:
            if abs(len(candidate) - len(token)) > maximum_distance:
                continue
            edit_distance = damerau_levenshtein_distance(token, candidate)
            if edit_distance > maximum_distance:
                continue
            similarity = 1.0 - edit_distance / max(len(token), len(candidate))
            minimum_similarity = 0.5 if len(token) <= 4 else 0.7
            if similarity < minimum_similarity:
                continue
            priority = 2 if candidate in GREETING_TERMS else (
                1 if candidate in INSURANCE_TERMS else 0
            )
            candidates.append(
                (
                    edit_distance,
                    -priority,
                    -self.frequencies_.get(candidate, 0),
                    candidate,
                )
            )
        return min(candidates)[-1] if candidates else token

    @staticmethod
    def _is_variant_of_controlled_term(token: str) -> bool:
        if token in CONTROLLED_TERMS:
            return False
        correction_targets = INSURANCE_TERMS | CONVERSATIONAL_TERMS
        maximum_distance = _maximum_edit_distance(token)
        return any(
            abs(len(candidate) - len(token)) <= maximum_distance
            and damerau_levenshtein_distance(token, candidate)
            <= maximum_distance
            for candidate in correction_targets
        )
