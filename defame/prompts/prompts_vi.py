"""Vietnamese-specialized prompt classes for fact-checking Vietnamese content."""

from typing import Collection
from pathlib import Path

from defame.common import Report, Label, Claim, Prompt, Content
from defame.common.label import DEFAULT_LABEL_DEFINITIONS
from defame.evidence_retrieval.integrations.search.common import Source
from defame.utils.parsing import (remove_non_symbols, extract_last_code_span, 
                                   find_code_span, extract_last_paragraph)
from config.globals import working_dir


class VietnameseJudgePrompt(Prompt):
    """Vietnamese-specific judge prompt for better Vietnamese language understanding."""
    template_file_path = working_dir / "defame/prompts/vi/judge_vi.md"
    retry_instruction = ("(Đừng quên chọn một tùy chọn từ Các Lựa chọn Quyết định "
                         "và đặt nó trong dấu backtick như `thế này`)")

    def __init__(self, doc: Report,
                 classes: Collection[Label],
                 class_definitions: dict[Label, str] = None,
                 extra_rules: str = None):
        if class_definitions is None:
            class_definitions = DEFAULT_LABEL_DEFINITIONS
        self.classes = classes
        class_str = '\n'.join([f"* `{cls.value}`: {remove_non_symbols(class_definitions[cls])}"
                               for cls in classes])
        placeholder_targets = {
            "[DOC]": str(doc),
            "[CLASSES]": class_str,
            "[EXTRA_RULES]": "" if extra_rules is None else remove_non_symbols(extra_rules),
        }
        super().__init__(placeholder_targets=placeholder_targets)

    def extract(self, response: str) -> dict | str | None:
        from defame.prompts.prompts import extract_verdict
        verdict = extract_verdict(response, classes=self.classes)
        if verdict is None:
            return None
        else:
            return dict(verdict=verdict, response=response)


class VietnamesePoseQuestionsPrompt(Prompt):
    """Vietnamese-specific question posing prompt."""
    template_file_path = working_dir / "defame/prompts/vi/pose_questions_vi.md"

    def __init__(self, doc: Report, n_questions: int = 10):
        placeholder_targets = {
            "[CLAIM]": doc.claim,
            "[N_QUESTIONS]": n_questions
        }
        super().__init__(placeholder_targets=placeholder_targets)

    def extract(self, response: str) -> dict:
        questions = find_code_span(response)
        return dict(
            questions=questions,
            response=response,
        )


class VietnameseProposeQueries(Prompt):
    """Vietnamese-specific query proposal prompt."""
    template_file_path = working_dir / "defame/prompts/vi/propose_queries_vi.md"

    def __init__(self, question: str, doc: Report):
        placeholder_targets = {
            "[DOC]": doc,
            "[QUESTION]": question,
        }
        super().__init__(placeholder_targets=placeholder_targets)

    def extract(self, response: str) -> dict:
        from defame.prompts.prompts import extract_queries
        queries = extract_queries(response)
        return dict(
            queries=queries,
            response=response,
        )


class VietnameseAnswerQuestion(Prompt):
    """Vietnamese-specific answer generation prompt."""
    template_file_path = working_dir / "defame/prompts/vi/answer_question_vi.md"

    def __init__(self, question: str, result: Source, doc: Report):
        placeholder_targets = {
            "[DOC]": doc,
            "[QUESTION]": question,
            "[RESULT]": result,
        }
        super().__init__(placeholder_targets=placeholder_targets)

    def extract(self, response: str) -> dict:
        """Extract result ID and answer to the question from response"""
        answered = "NONE" not in response and "None" not in response

        out = dict(
            answered=answered,
            response=response,
        )

        if answered:
            answer = extract_last_paragraph(response)
            out.update(dict(answer=answer))

        return out


class VietnameseSummarizeDocPrompt(Prompt):
    """Vietnamese-specific document summarization prompt."""
    template_file_path = working_dir / "defame/prompts/vi/summarize_doc_vi.md"

    def __init__(self, doc: Report):
        super().__init__(placeholder_targets={"[DOC]": doc})


class VietnameseDecomposePrompt(Prompt):
    """Vietnamese-specific decomposition prompt."""
    template_file_path = working_dir / "defame/prompts/vi/decompose_vi.md"

    def __init__(self, content: Content):
        self.content = content
        placeholder_targets = {
            "[CONTENT]": content,
            "[INTERPRETATION]": content.interpretation
        }
        super().__init__(placeholder_targets=placeholder_targets)

    def extract(self, response: str) -> dict:
        statements = response.split("\n\n")
        return dict(statements=[Claim(s.strip(), context=self.content) for s in statements if s],
                    response=response)
