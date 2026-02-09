from datasets import load_dataset

from defame.common import Label, Claim, Content
from defame.eval.benchmark import Benchmark
from defame.evidence_retrieval.tools import Search, Geolocate
import os

# defame/data/vifactcheck/test-00000-of-00001.parquet
file_path = os.path.join("vifactcheck", "test-00000-of-00001.parquet") 

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
    
    extra_prepare_rules = """* Claim đã bao gồm context đi kèm, đây là thông tin **bắt buộc** để hiểu đúng ý nghĩa.
        * **Không được bỏ qua context**.
        * Sử dụng context để làm rõ các thực thể, thời điểm, phạm vi và bối cảnh trước khi tìm kiếm bằng chứng.
        * **Không suy diễn hoặc thêm bất kỳ thông tin context nào ngoài những gì đã được cung cấp trong Claim.**"""
    
    available_actions = [Search]
    
    def __init__(self, variant="test"):
        """Initialize ViFactCheck benchmark.
        
        Args:
            variant: Dataset split to use ('train', 'test', or 'dev')
        """
        self.split = variant
        
        super().__init__(variant, file_path=file_path)
    
    def _load_data(self) -> list[dict]:
        """Load dataset from Hugging Face.
        
        Returns:
            List of dataset instances with id, input (Claim), label, and evidence
        """
        # Load dataset from Hugging Face
        # dataset = load_dataset("tranthaihoa/vifactcheck", split=self.split)
        
        # Load dataset from file
        # dataset = load_dataset("vifactcheck", split=self.split, data_files= {'{variant}': self.file_path})

        dataset = load_dataset(
            "parquet", 
            split=self.split, 
            data_files={self.split: str(self.file_path)}
        )

        data = []
        for i, row in enumerate(dataset):
            identifier = f"{self.split}_{i}"
            entry = {
                "id": identifier,
                "input": Claim(row['Statement'], id=identifier, context=Content(row.get('Context', ''))),
                "label": self.class_mapping[row['labels']],
                "evidence": row.get('Context', ''),  # Store evidence for reference
                "justification": ""  # ViFactCheck doesn't provide ground truth justifications
            }
            data.append(entry)
        
        return data
