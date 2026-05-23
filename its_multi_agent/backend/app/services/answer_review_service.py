import re
from typing import List

from schemas.answer_review import CandidateAnswer, EvidenceItem, ReviewVerdict


class AnswerReviewService:
    STOPWORDS = {
        "the",
        "a",
        "an",
        "and",
        "or",
        "to",
        "of",
        "for",
        "is",
        "are",
        "be",
        "can",
        "should",
        "you",
        "your",
        "that",
        "this",
        "with",
        "first",
    }

    def review_answer(self, candidate_answer: CandidateAnswer, evidence_items: List[EvidenceItem]) -> ReviewVerdict:
        if not evidence_items:
            return ReviewVerdict(
                status="review_unavailable",
                summary="No retrieval evidence was available for review.",
                should_downgrade=True,
            )

        if any(item.support_level == "conflicts" for item in evidence_items):
            return ReviewVerdict(
                status="conflicting",
                summary="Evidence contains direct conflicts with the candidate answer.",
                should_downgrade=True,
            )

        candidate_text = self._normalize(candidate_answer.answer)
        if not candidate_text:
            return ReviewVerdict(
                status="review_unavailable",
                summary="Candidate answer is empty.",
                should_downgrade=True,
            )

        similarity = max(
            (self._similarity(candidate_text, self._normalize(item.snippet)) for item in evidence_items),
            default=0.0,
        )
        if similarity >= 0.35:
            return ReviewVerdict(
                status="supported",
                summary="At least one evidence item materially overlaps with the answer.",
                should_downgrade=False,
            )

        return ReviewVerdict(
            status="unsupported",
            summary="Available evidence does not directly support the candidate answer.",
            should_downgrade=True,
        )

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip().lower())

    def _similarity(self, left: str, right: str) -> float:
        if not left or not right:
            return 0.0
        if left in right or right in left:
            return 1.0
        if self._contains_cjk(left) or self._contains_cjk(right):
            return self._char_ngram_similarity(left, right)
        return self._word_overlap_similarity(left, right)

    @staticmethod
    def _contains_cjk(text: str) -> bool:
        return bool(re.search(r"[\u4e00-\u9fff]", text))

    @staticmethod
    def _char_ngram_similarity(left: str, right: str) -> float:
        left_ngrams = AnswerReviewService._ngrams(re.sub(r"\s+", "", left))
        right_ngrams = AnswerReviewService._ngrams(re.sub(r"\s+", "", right))
        if not left_ngrams or not right_ngrams:
            return 0.0
        overlap = left_ngrams & right_ngrams
        return len(overlap) / max(1, min(len(left_ngrams), len(right_ngrams)))

    def _word_overlap_similarity(self, left: str, right: str) -> float:
        left_tokens = self._tokenize_words(left)
        right_tokens = self._tokenize_words(right)
        if not left_tokens or not right_tokens:
            return 0.0
        overlap = left_tokens & right_tokens
        return len(overlap) / max(1, len(left_tokens))

    def _tokenize_words(self, text: str) -> set[str]:
        tokens = {
            token
            for token in re.findall(r"[a-z0-9]+", text)
            if token not in self.STOPWORDS and len(token) > 2
        }
        return tokens

    @staticmethod
    def _ngrams(text: str) -> set[str]:
        if len(text) < 2:
            return {text} if text else set()
        return {text[index:index + 2] for index in range(len(text) - 1)}


answer_review_service = AnswerReviewService()
