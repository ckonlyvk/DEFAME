"""Vietnamese-specialized Judge for Vietnamese fact-checking."""

import dataclasses
from typing import Collection

from defame.common import Report, Model, Label
from defame.common.label import DEFAULT_LABEL_DEFINITIONS
from defame.modules.judge import Judge
from defame.prompts.prompts_vi import VietnameseJudgePrompt


class VietnameseJudge(Judge):
    """Vietnamese-specialized judge that uses Vietnamese prompts for better 
    understanding of Vietnamese context and language nuances."""

    def __init__(self,
                 llm: Model,
                 classes: list[Label],
                 class_definitions: dict[Label, str] = None,
                 extra_rules: str = None):
        super().__init__(llm, classes, class_definitions, extra_rules)

    def judge(self, doc: Report, is_final: bool = True) -> Label:
        """Override to use Vietnamese-specific prompt."""
        classes = self.classes.copy()

        # If this is a non-final judgement (i.e. there are follow-up retrievals/actions allowed)
        # enable to predict NEI (otherwise fact-check would always end here)
        if not is_final:
            classes.add(Label.NEI)

        # Use Vietnamese prompt instead of default
        prompt = VietnameseJudgePrompt(doc, classes, self.class_definitions, self.extra_rules)
        return self._generate_verdict(prompt)
