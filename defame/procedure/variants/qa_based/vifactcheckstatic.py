from defame.common import Report, Label, logger
from defame.procedure.variants.qa_based.base_vi import VietnameseQABased
from defame.utils.console import light_blue
from typing import Any

class ViFactCheckStatic(VietnameseQABased):
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
        """Override to use provided context if available, or search otherwise."""
        
        logger.log(light_blue(f"Answering question: {question}"))
        self.actor.reset()

        search_results = []
        
        # Check if context is available in the claim
        if doc and doc.claim and doc.claim.context and str(doc.claim.context).strip():
            from defame.evidence_retrieval.integrations.search.common import WebSource
            
            # Create a WebSource from the context
            context_source = WebSource(
                reference="local_context",
                title="Provided Context",
                content=doc.claim.context,
                preview=str(doc.claim.context)[:200] + "..."
            )
            search_results = [context_source]
            
        else:
            # Stage 3: Generate search queries
            queries = self.propose_queries_for_question(question, doc)
            if len(queries) == 0:
                return None

            # Execute searches and gather all results
            search_results = self.retrieve_sources(queries)

        # Step 4: Answer generation
        if len(search_results) > 0:
            answer_result = self.generate_answer(question, search_results, doc)
            
            return answer_result
        
        return None

    def apply_to(self, doc: Report) -> (Label, dict[str, Any]):
        # This method receives a SINGLE claim (extraction already done by FactChecker if needed)
        # We just need to verify the claim

        # Stage 1: Start Verification
        
        questions = self._pose_questions(no_of_questions=3, doc=doc)
        
        # Stage 3: Literature Review - Search and answer questions
        q_and_a = []
        for idx, question in enumerate(questions, 1):
            # Answer the question (will emit source updates via approach_question)
            answer_dict_list = self.approach_question_batch([question], doc)
            
            for answer_dict in answer_dict_list:
                # Check if answer is valid
                answer_text = answer_dict.get('answer', '')
                if answer_text and answer_text.strip() and answer_text != "None" and answer_text != "[]":
                     q_and_a.append(answer_dict)
                     logger.log(light_blue(f"Answered question: {answer_dict}"))
                else:
                     logger.log(light_blue(f"Skipping empty answer for question: {question}"))
        
        # Stage 4: Veracity Prediction (Conclusion)
        
        label = self.judge.judge(doc)

        return label, dict(q_and_a=q_and_a)