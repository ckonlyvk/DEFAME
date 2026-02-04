"""Vietnamese-specific running example for multimodal fact-check using ViFactCheck procedure."""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from defame.fact_checker import FactChecker

# Use Vietnamese-specialized ViFactCheck procedure
fact_checker = FactChecker(llm="gpt_4o", procedure_variant="vifactcheck")

# Vietnamese claim to test
claim = ["VNG là công ty công nghệ đầu tiên của Việt Nam được niêm yết trên sàn chứng khoán Mỹ (NASDAQ)"]

# Run fact-check
report, _ = fact_checker.check_content(claim)

# Save report
report.save_to("out/fact-check-vi")

print(f"\n{'='*60}")
print("ViFactCheck Test Completed")
print(f"{'='*60}")
print(f"Claim: {claim[0]}")
print(f"Verdict: {report.label}")
print(f"Report saved to: out/fact-check-vi")
print(f"{'='*60}\n")
