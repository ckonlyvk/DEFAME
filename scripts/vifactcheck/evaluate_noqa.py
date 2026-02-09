if __name__ == '__main__':  # evaluation uses multiprocessing
    from defame.eval.evaluate import evaluate
# Run by command: python scripts/vifactcheck/evaluate_noqa.py
    evaluate(
        llm="ollama_gptoss_cloud",
        tools_config=dict(
            searcher=dict(
                search_config=dict(
                    google=dict(),
                ),
                limit_per_search=3
            )
        ),
        fact_checker_kwargs=dict(
            procedure_variant="summary/no_qa_vi",  # Use Vietnamese NoQA
            interpret=False,
            decompose=False,
            decontextualize=True,
            filter_check_worthy=False,
            restrict_results_to_claim_date = True,
            allow_fact_checking_sites = True,
            max_iterations=3,
            max_result_len=64_000,  # characters
        ),
        llm_kwargs=dict(temperature=0.01),
        benchmark_name="vifactcheck",  # Use ViFactCheck benchmark
        benchmark_kwargs=dict(variant="test"),  # test, train, or dev
        allowed_actions=["search"],
        n_samples=10,  # Start with small sample for testing
        sample_ids=None, # list of integers
        random_sampling=False,
        print_log_level="log",
        n_workers=1,  # Use 1 worker for initial testing
    )
