import multiprocessing
import sys
import time
from typing import Sequence, Any
from datetime import datetime

import numpy as np
from ezmm import Item

from defame.common import logger, Claim, Content, Report, Label, Action, Model
from defame.common.label import DEFAULT_LABEL_DEFINITIONS
from defame.common.modeling import make_model
from defame.common.vifact_claim import ViFactClaim
from defame.modules.actor import Actor
from defame.modules.claim_extractor import ClaimExtractor
from defame.modules.doc_summarizer import DocSummarizer
from defame.modules.judge import Judge
from defame.modules.judge_vi import VietnameseJudge
from defame.modules.planner import Planner
from defame.procedure import get_procedure
from defame.evidence_retrieval import scraper, Tool
from defame.evidence_retrieval.tools import initialize_tools
from defame.evidence_retrieval.tools.tool import get_available_actions
from defame.utils.console import gray, light_blue, bold, sec2mmss


class FactChecker:
    """The core class for end-to-end fact verification."""
    
    default_procedure = "defame"

    def __init__(self,
                 llm: str | Model = "gpt_4o_mini",  # Mô hình ngôn ngữ sẽ sử dụng
                 llm_kwargs: dict = None,  # Các tham số khởi tạo cho mô hình
                 tools: list[Tool] = None,  # Danh sách các công cụ đã khởi tạo
                 tools_config: dict = None,  # Cấu hình để khởi tạo công cụ nếu tools chưa có
                 available_actions: list[Action] = None,  # Danh sách các hành động (Action) khả dụng
                 procedure_variant: str = None,  # Biến thể quy trình kiểm chứng (procedure) sẽ chạy
                 interpret: bool = False,  # Có thực hiện bước diễn giải (interpret) claim hay không
                 decompose: bool = False,  # Có chia nhỏ (decompose) claim phức tạp hay không
                 decontextualize: bool = False,  # Có tách ngữ cảnh (decontextualize) cho claim hay không
                 filter_check_worthy: bool = False,  # Có lọc các claim đáng kiểm chứng hay không
                 max_iterations: int = 5,  # Số vòng lặp tối đa cho quá trình kiểm chứng
                 max_result_len: int = None,  # Độ dài tối đa của kết quả trả về
                 restrict_results_to_claim_date: bool = True,  # Giới hạn tìm kiếm thông tin trước ngày diễn ra claim
                 allow_fact_checking_sites: bool = True,  # Cho phép sử dụng thông tin từ các trang fact-check khác
                 classes: Sequence[Label] = None,  # Danh sách các nhãn kết luận (VD: SUPPORTED, REFUTED)
                 class_definitions: dict[Label, str] = None,  # Định nghĩa chi tiết cho từng nhãn
                 extra_prepare_rules: str = None,  # Các quy tắc bổ sung cho bước chuẩn bị (extract claim)
                 extra_plan_rules: str = None,  # Các quy tắc bổ sung cho bước lập kế hoạch (planner)
                 extra_judge_rules: str = None,  # Các quy tắc bổ sung cho bước đánh giá (judge)
                 device: str = None):  # Thiết bị tính toán (VD: 'cuda', 'cpu')

        if tools_config is None:
            tools_config = dict(searcher=None)

        if llm_kwargs is None:
            llm_kwargs = {}

        if device is not None:
            llm_kwargs.update(device=device)

        self.llm = make_model(llm, **llm_kwargs) if isinstance(llm, str) else llm

        is_vifactcheck = procedure_variant in {"vifactcheck", "summary/no_qa_vi"}
        # Determine decompose prompt based on procedure
        decompose_prompt = None
        if procedure_variant in ["vifactcheck", "vifactcheckstatic"]:
            from defame.prompts.prompts_vi import VietnameseDecomposePrompt
            decompose_prompt = VietnameseDecomposePrompt

        # Determine decontextualize prompt based on procedure
        decontextualize_prompt = None
        if is_vifactcheck:
            from defame.prompts.prompts_vi import VietnameseDecontextualizePrompt
            decontextualize_prompt = VietnameseDecontextualizePrompt

        self.claim_extractor = ClaimExtractor(llm=self.llm,
                                              prepare_rules=extra_prepare_rules,
                                              interpret=interpret,
                                              decompose=decompose,
                                              decontextualize=decontextualize,
                                              filter_check_worthy=filter_check_worthy,
                                              decompose_prompt_cls=decompose_prompt,
                                              decontextualize_prompt_cls=decontextualize_prompt)

        if classes is None:
            if class_definitions is None:
                classes = [Label.SUPPORTED, Label.NEI, Label.REFUTED]
                class_definitions = DEFAULT_LABEL_DEFINITIONS
            else:
                classes = list(class_definitions.keys())

        self.extra_prepare_rules = extra_prepare_rules
        self.max_iterations = max_iterations
        self.max_result_len = max_result_len
        self.restrict_results_to_claim_date = restrict_results_to_claim_date
        scraper.allow_fact_checking_sites = allow_fact_checking_sites

        if tools is None:
            tools = initialize_tools(tools_config, llm=self.llm)

        available_actions = get_available_actions(tools, available_actions)

        # Initialize fact-checker modules
        self.planner = Planner(valid_actions=available_actions,
                               llm=self.llm,
                               extra_rules=extra_plan_rules)

        self.actor = Actor(tools=tools)

        self.judge = Judge(llm=self.llm,
                           classes=classes,
                           class_definitions=class_definitions,
                           extra_rules=extra_judge_rules)
        if procedure_variant in ["vifactcheck", "vifactcheckstatic"]:
            self.judge = VietnameseJudge(llm=self.llm,
                           classes=classes,
                           class_definitions=class_definitions,
                           extra_rules=extra_judge_rules)

        # Determine summarizer prompt based on procedure
        summarizer_prompt = None
        if procedure_variant in ["vifactcheck", "vifactcheckstatic"]:
            from defame.prompts.prompts_vi import VietnameseSummarizeDocPrompt
            summarizer_prompt = VietnameseSummarizeDocPrompt

        self.doc_summarizer = DocSummarizer(self.llm, prompt_cls=summarizer_prompt)

        if procedure_variant is None:
            procedure_variant = self.default_procedure

        self.procedure = get_procedure(procedure_variant,
                                       llm=self.llm,
                                       actor=self.actor,
                                       judge=self.judge,
                                       planner=self.planner,
                                       max_iterations=self.max_iterations)

    def extract_claims(self, content: Content | list[str | Item]) -> list[Claim]:
        if not isinstance(content, Content):
            content = Content(content)
        return self.claim_extractor.extract_claims(content)

    def check_content(self, content: Content | list[str | Item]) -> tuple[Label, list[Report], list[dict[str, Any]]]:
        """
        Fact-checks the given content ent-to-end by first extracting all check-worthy claims and then
        verifying each claim individually. Returns the aggregated veracity and the list of corresponding
        fact-checking documents, one doc per claim.
        """
        from defame.common import StageEmitter
        
        # Define ad-hoc stages for extraction if not available globally
        class ExtractionStage:
            EXTRACT_CLAIMS = (0, "Phát hiện câu claim", "Tách câu cần kiểm chứng từ tin tức")
            
        start = time.time()

        # --- Stage 0: Extract Claims ---
        extract_event = StageEmitter.emit(
            ExtractionStage.EXTRACT_CLAIMS,
            status='inprogress',
            detail='Đang phân tích và trích xuất các luận điểm...'
        )

        try:
            claims = self.extract_claims(content)
            
            # Update extraction event
            StageEmitter.update(
                extract_event,
                status='complete',
                detail=f'Tìm thấy {len(claims)} luận điểm cần kiểm chứng.'
            )
        except Exception as e:
            StageEmitter.update(
                extract_event,
                status='error',
                detail=f'Lỗi khi trích xuất: {str(e)}'
            )
            logger.error(f"Error extracting claims: {e}")
            # Fallback to treating content as single claim if possible, or re-raise
            # For now, re-raising or returning empty might be best.
            # Let's fallback to creating a single claim from content if it's a string
            if isinstance(content, str):
                 claims = [Claim(content)]
                 StageEmitter.update(extract_event, detail="Không trích xuất được, sử dụng toàn bộ văn bản làm luận điểm.")
            else:
                 raise e

        # Verify each single extracted claim
        docs = []
        metas = []
        
        # Helper class for ad-hoc group stages
        class AdHocStage:
            def __init__(self, id, title, desc):
                self.value = id
                self.title = title
                self.description = desc
                self.name = "CLAIM_GROUP"
        
        # Verify loop with grouping
        for i, claim in enumerate(claims):
            # Create a group for this claim
            group_title = f"Luận điểm {i+1}: {str(claim)}"
            
            # Use helper class to ensure StageEmitter gets correct ID and title
            group_stage = AdHocStage(100 + i, group_title, str(claim))
            
            group_id = StageEmitter.emit(
                stage=group_stage,
                status='inprogress',
                detail=str(claim)
            )

            # Set context for children events
            with StageEmitter.parent(group_id):
                try:
                    doc, meta = self.verify_claim(claim)
                    docs.append(doc)
                    metas.append(meta)
                    target_dir = logger.target_dir if logger.target_dir else "out/fact_check"
                    doc.save_to(target_dir)
                    
                    # Update group status to complete
                    # We can add the verdict to the group header/detail
                    verdict_map = {
                        'SUPPORTED': 'ĐƯỢC XÁC NHẬN',
                        'REFUTED': 'BỊ BÁC BỎ',
                        'NEI': 'CHƯA ĐỦ BẰNG CHỨNG'
                    }
                    # Get clean name from Enum
                    verdict_key = getattr(doc.verdict, 'name', str(doc.verdict))
                    # Handle case where str(doc.verdict) returns 'Label.NEI'
                    if 'Label.' in verdict_key:
                        verdict_key = verdict_key.split('.')[-1]
                        
                    verdict_text = verdict_map.get(verdict_key, verdict_key)
                    
                    StageEmitter.update(
                        group_id, 
                        status='complete',
                        detail=f"{str(claim)}\n\nKết luận: {verdict_text}"
                    )
                    
                except Exception as e:
                    logger.error(f"Error verifying claim {claim}: {e}")
                    # Update group to error
                    StageEmitter.update(
                        group_id,
                        status='error',
                        detail=f"{str(claim)}\n\nLỗi: {str(e)}"
                    )
                    # We might still want to append None or a failed doc to keep indices aligned if needed
                    # But check_content return type expects Report. 
                    # We'll skip adding to docs/metas to avoid breaking aggregation?
                    # Or better, create a dummy failed Report
                    # For now just continue

        aggregated_veracity = aggregate_predictions([doc.verdict for doc in docs]) if docs else Label.NEI
        logger.log(bold(f"So, the overall veracity is: {aggregated_veracity.value}"))
        fc_duration = time.time() - start
        logger.log(f"Fact-check took {sec2mmss(fc_duration)}.")
        return aggregated_veracity, docs, metas

    def verify_claim(self, claim: Claim | list[str | Item]) -> tuple[Report, dict[str, Any]]:
        """Takes an (atomic, decontextualized, check-worthy) claim and fact-checks it.
        This is the core of the fact-checking implementation. Here, the fact-checking
        document is constructed incrementally."""

        if (isinstance(claim, ViFactClaim) and claim.context and self.claim_extractor):
            claim = self.claim_extractor.decontextualize(claim)

        if not isinstance(claim, Claim):
            claim = Claim(claim)

        logger.info(f"Verifying claim.", send=True)
        logger.info(f"{bold(str(claim))}")

        stats = {}
        self.actor.reset()  # remove all past search evidences
        self.actor.set_current_claim_id(claim.id)
        if self.restrict_results_to_claim_date:
            # Set the restriction to midnight of the claim date
            restriction_time = datetime.combine(claim.date, datetime.min.time()) if claim.date else None
            self.actor.set_search_date_restriction(restriction_time)
        if not self.llm:
            worker_name = multiprocessing.current_process().name
            logger.critical(f"No LLM was loaded. Stopping execution for {worker_name}.")
            sys.exit(1)  # Exits the process for this worker
        self.llm.reset_stats()

        start = time.time()
        doc = Report(claim)

        # Depending on the specified procedure variant, perform the fact-check
        label, meta = self.procedure.apply_to(doc)

        # Finalize the fact-check
        doc.add_reasoning("## Final Judgement\n" + self.judge.get_latest_reasoning())

        # Summarize the fact-check and use the summary as justification
        if label == Label.REFUSED_TO_ANSWER:
            logger.warning("The model refused to answer.")
        else:
            doc.justification = self.doc_summarizer.summarize(doc)
            logger.info(bold(f"The claim '{light_blue(str(claim))}' is {label.value}."))
            logger.info(f'Justification: {gray(doc.justification)}')
        doc.verdict = label

        stats["Duration"] = time.time() - start
        stats["Model"] = self.llm.get_stats()
        stats["Tools"] = self.actor.get_tool_stats()
        meta["Statistics"] = stats
        return doc, meta


def aggregate_predictions(veracities: Sequence[Label]) -> Label:
    # If all predicted labels are the same label, return that label
    if len(set(veracities)) == 1:
        return veracities[0]

    # Otherwise, apply this aggregation
    veracities = np.array(veracities)
    if np.any(veracities == Label.REFUSED_TO_ANSWER):
        return Label.REFUSED_TO_ANSWER
    elif np.any(veracities == Label.REFUTED):
        return Label.REFUTED
    elif np.any(veracities == Label.CONFLICTING):
        return Label.CONFLICTING
    elif np.any(veracities == Label.CHERRY_PICKING):
        return Label.CHERRY_PICKING
    else:
        return Label.NEI
