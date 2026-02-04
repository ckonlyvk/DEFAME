"""Vietnamese-specialized QA-based procedure for Vietnamese fact-checking."""

from abc import ABC
from typing import Optional

from defame.common import Report, logger
from defame.evidence_retrieval.tools import Search
from defame.evidence_retrieval.integrations.search.common import WebSource
from defame.procedure.variants.qa_based.base import QABased
from defame.prompts.prompts_vi import (VietnamesePoseQuestionsPrompt, 
                                       VietnameseProposeQueries, 
                                       VietnameseAnswerQuestion)
from defame.utils.console import light_blue


class VietnameseQABased(QABased, ABC):
    """Vietnamese-specialized QA-based procedure that uses Vietnamese prompts 
    for all QA stages to better handle Vietnamese language and context."""

    def _pose_questions(self, no_of_questions: int, doc: Report) -> list[str]:
        """Generates questions using Vietnamese-specific prompt."""
        prompt = VietnamesePoseQuestionsPrompt(doc, n_questions=no_of_questions)
        response = self.llm.generate(prompt)
        logger.warning("VietnameseQABased - _pose_questions: ", response)
        if response is None:
            return []
        else:
            return response["questions"]

    def propose_queries_for_question(self, question: str, doc: Report) -> list[Search]:
        """Proposes search queries using Vietnamese-specific prompt."""
        prompt = VietnameseProposeQueries(question, doc)

        n_attempts = 0
        while n_attempts < self.max_attempts:
            n_attempts += 1
            response = self.llm.generate(prompt)

            if response is None:
                continue

            queries: list = response["queries"]

            if len(queries) > 0:
                return queries

            logger.log("No new actions were found. Retrying...")

        logger.warning("Got no search query, dropping this question.")
        return []

    def attempt_answer_question(self, question: str, result: WebSource, doc: Report) -> Optional[str]:
        """Generates an answer using Vietnamese-specific prompt."""
        prompt = VietnameseAnswerQuestion(question, result, doc)
        out = self.llm.generate(prompt, max_attempts=3)
        if out is not None and out["answered"]:
            return out["answer"]
