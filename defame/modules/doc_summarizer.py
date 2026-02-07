from defame.common.report import Report
from defame.common.modeling import Model
from defame.prompts.prompts import SummarizeDocPrompt


class DocSummarizer:
    """Summarizes a given, finished fact-checking document. The resulting summary is
    equivalent to the justification of the verdict."""

    def __init__(self, llm: Model, prompt_cls: type = None):
        if prompt_cls is None:
            self.prompt_cls = SummarizeDocPrompt
        else:
            self.prompt_cls = prompt_cls
        self.llm = llm

    def summarize(self, doc: Report) -> str:
        summarize_doc_prompt = self.prompt_cls(doc)
        summary = self.llm.generate(summarize_doc_prompt)
        return summary
