"""Minimal running example for a multimodal fact-check."""

from ezmm import Image

from defame.fact_checker import FactChecker

fact_checker = FactChecker(llm="gpt_4o", procedure_variant="infact")
claim = ["VNG là công ty công nghệ đầu tiên của Việt Nam được niêm yết trên sàn chứng khoán Mỹ (NASDAQ)"]
report, _ = fact_checker.check_content(claim)
report.save_to("out/fact-check")
