from typing import Any

from defame.common import Report, Label, StageEmitter
from defame.procedure.variants.qa_based.base_vi import VietnameseQABased
from enum import Enum
from defame.common import logger
from defame.utils.console import light_blue
from typing import Optional

class VerificationStage(Enum):
    EXTRACT_CLAIMS = (0, "Phát hiện câu claim", "Tách câu cần kiểm chứng từ tin tức")
    START_VERIFICATION = (1, "Bắt đầu kiểm chứng", "Xác định vấn đề hoặc hiện tượng cần kiểm chứng")
    FORMULATE_QUESTION = (2, "Đặt câu hỏi kiểm chứng", "Xây dựng câu hỏi hoặc giả thuyết nghiên cứu")
    LITERATURE_REVIEW = (3, "Tìm tài liệu cho câu hỏi: {question}", "Thu thập và phân tích tài liệu liên quan")
    CONCLUSION = (4, "Kết luận", "Đưa ra kết luận dựa trên kết quả phân tích và kiểm chứng")

    def __init__(self, value, title, description):
        self._value_ = value
        self.title = title
        self.description = description

class ViFactCheck(VietnameseQABased):
    """Vietnamese-specialized fact-checking procedure.
    
    This procedure is optimized for Vietnamese language fact-checking with:
    - Increased number of questions to capture Vietnamese linguistic nuances
    - Vietnamese-aware search query generation
    - Better handling of Vietnamese-specific sources and content
    - Enhanced question posing that accounts for Vietnamese grammar and context
    - Real-time stage tracking for UI display
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._current_lit_event = None  # Track current literature review event
    
    def approach_question(self, question: str, doc: Report = None):
        """Override to emit source information to UI."""
        
        logger.log(light_blue(f"Answering question: {question}"))
        self.actor.reset()

        # Stage 3: Generate search queries
        queries = self.propose_queries_for_question(question, doc)
        if len(queries) == 0:
            return None

        # Execute searches and gather all results
        search_results = self.retrieve_sources(queries)
        
        # Emit source information based on what we found
        if self._current_lit_event:
            if len(search_results) > 0:
                # Extract URLs from search results
                source_urls = []
                for result in search_results:
                    if hasattr(result, 'url') and result.url:
                        source_urls.append(result.url)
                
                # Update with source information
                if source_urls:
                    urls_text = '\n'.join(f'• {url}' for url in source_urls[:5])  # Show max 5
                    detail_text = f'🔍 Tìm thấy {len(source_urls)} nguồn:\n{urls_text}'
                    if len(source_urls) > 5:
                        detail_text += f'\n... và {len(source_urls) - 5} nguồn khác'
                    
                    StageEmitter.update(
                        self._current_lit_event,
                        detail=detail_text
                    )
            else:
                # No sources found
                StageEmitter.update(
                    self._current_lit_event,
                    detail='⚠️ Không tìm thấy tài liệu nào'
                )

        # Step 4: Answer generation
        if len(search_results) > 0:
            answer_result = self.generate_answer(question, search_results, doc)
            
            # Update with final answer
            if self._current_lit_event and answer_result:
                answer_text = answer_result.get('answer', 'Không có câu trả lời')[:200]
                source_count = len(search_results)
                StageEmitter.update(
                    self._current_lit_event,
                    detail=f'✅ Đã phân tích {source_count} nguồn\n✓ Câu trả lời: {answer_text}'
                )
            
            return answer_result
        
        return None

    def apply_to(self, doc: Report) -> (Label, dict[str, Any]):
        # This method receives a SINGLE claim (extraction already done by FactChecker if needed)
        # We just need to verify the claim

        # Stage 1: Start Verification
        claim_display = str(doc.claim)
        start_event = StageEmitter.emit(
            VerificationStage.START_VERIFICATION,
            status='inprogress',
            detail=f'Đang phân tích tuyên bố: "{claim_display}"'
        )
        
        # Stage 2: Formulate Questions (Vietnamese-optimized)
        question_event = StageEmitter.emit(
            VerificationStage.FORMULATE_QUESTION,
            status='inprogress'
        )
        
        questions = self._pose_questions(no_of_questions=3, doc=doc)
        
        # Format question list outside f-string to avoid backslash error
        question_list = ", ".join(f'"{q}"' for q in questions)
        StageEmitter.update(
            question_event,
            status='complete',
            detail=f'Đã tạo {len(questions)} câu hỏi: {question_list}'
        )
        
        # Complete start verification stage
        StageEmitter.update(start_event, status='complete')
        
        # Stage 3: Literature Review - Search and answer questions
        q_and_a = []
        for idx, question in enumerate(questions, 1):
            # Create new event for each question
            lit_event = StageEmitter.emit(
                VerificationStage.LITERATURE_REVIEW,
                status='inprogress',
                metadata={'question': question[:200]}  # Format title with question
            )
            
            # Store current event ID for approach_question to use
            self._current_lit_event = lit_event
            
            # Answer the question (will emit source updates via approach_question)
            answer_dict = self.approach_question_batch([question], doc)
            q_and_a.extend(answer_dict)
            logger.log(light_blue(f"Answered question: {answer_dict}"))
            
            # Clear current event
            self._current_lit_event = None
            
            # Mark as complete
            StageEmitter.update(lit_event, status='complete')
        
        # Stage 4: Veracity Prediction (Conclusion)
        conclusion_event = StageEmitter.emit(
            VerificationStage.CONCLUSION,
            status='inprogress',
            detail='Đang phân tích bằng chứng và đưa ra kết luận...'
        )
        
        label = self.judge.judge(doc)
        
        # Map label to display text (True/False/Unknown)
        label_name = label.name if hasattr(label, 'name') else str(label).split('.')[-1]
        verdict_map = {
            'SUPPORTED': 'True',
            'REFUTED': 'False',
            'NEI': 'Unknown'
        }
        verdict_display = verdict_map.get(label_name, label_name)
        
        StageEmitter.update(
            conclusion_event,
            status='complete',
            detail=f'Tuyên bố {verdict_display}'
        )

        return label, dict(q_and_a=q_and_a)



