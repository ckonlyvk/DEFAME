from datasets import load_dataset

from defame.common import Label, Claim
from defame.eval.benchmark import Benchmark
from defame.evidence_retrieval.tools import Search, Geolocate


class ViFactCheck(Benchmark):
    """ViFactCheck: Vietnamese fact-checking benchmark dataset.
    
    A multi-domain news fact-checking benchmark for Vietnamese with 7,232 
    human-annotated claim-evidence pairs across 12 topics.
    
    Paper: ViFactCheck: A New Benchmark Dataset and Methods for Multi-domain 
    News Fact-Checking in Vietnamese (AAAI 2025)
    """
    name = "ViFactCheck"
    shorthand = "vifactcheck"
    
    is_multimodal = False
    
    # Label mapping from dataset integers to DEFAME Labels
    class_mapping = {
        0: Label.SUPPORTED,
        1: Label.REFUTED,
        2: Label.NEI
    }
    
    # Standard fact-checking label definitions
    class_definitions = {
        Label.SUPPORTED: 
            "Tuyên bố chính xác và được hỗ trợ bởi bằng chứng. "
            "The claim is accurate and supported by evidence.",
        Label.REFUTED: 
            "Tuyên bố sai và bị bác bỏ bởi bằng chứng. "
            "The claim is false and contradicted by evidence.",
        Label.NEI: 
            "Không có đủ thông tin để xác minh tuyên bố. "
            "There is not enough information to verify the claim."
    }
    
    extra_prepare_rules = """**Vietnamese Context**: This is a Vietnamese fact-checking task. 
    Pay attention to Vietnamese-specific context, sources, and cultural nuances.
    **Multi-domain**: Claims span 12 different domains including politics, health, technology, etc."""
    
    extra_plan_rules = """* **Use Vietnamese Sources**: Prioritize Vietnamese news sources and databases when searching for evidence.
    * **Cultural Context**: Consider Vietnamese cultural and political context when evaluating claims.
    * **Multi-domain Awareness**: Be aware that claims may come from various domains and adjust search strategies accordingly."""
    
    available_actions = [Search, Geolocate]
    
    def __init__(self, variant="test"):
        """Initialize ViFactCheck benchmark.
        
        Args:
            variant: Dataset split to use ('train', 'test', or 'dev')
        """
        self.split = variant
        # Don't pass file_path since we load from HuggingFace
        super().__init__(variant, file_path=None)
    
    def _load_data(self) -> list[dict]:
        """Load dataset from Hugging Face.
        
        Returns:
            List of dataset instances with id, input (Claim), label, and evidence
        """
        # Load dataset from Hugging Face
        dataset = load_dataset("tranthaihoa/vifactcheck", split=self.split)
        
        data = []
        for i, row in enumerate(dataset):
            identifier = f"{self.split}_{i}"
            entry = {
                "id": identifier,
                "input": Claim(row['Statement'], id=identifier),  # Positional argument, not keyword
                "label": self.class_mapping[row['labels']],
                "evidence": row.get('Context', ''),  # Store evidence for reference
                "justification": ""  # ViFactCheck doesn't provide ground truth justifications
            }
            data.append(entry)
        
        return data
