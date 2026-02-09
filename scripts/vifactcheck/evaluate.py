if __name__ == '__main__':  # evaluation uses multiprocessing
    from defame.eval.evaluate import evaluate
# Run by command: python scripts/vifactcheck/evaluate.py
    evaluate(
        llm="gpt_4o_mini",
        tools_config=dict(
            searcher=dict(
                search_config=dict(
                    google=dict(),
                ),
                limit_per_search=3
            ),
            geolocator=dict()
        ),
        fact_checker_kwargs=dict(
            procedure_variant="vifactcheckstatic",  # Use Vietnamese-optimized procedure
            interpret=False,
            decompose=False,
            decontextualize=False,
            filter_check_worthy=False,
            max_iterations=3,
            max_result_len=64_000,  # characters
        ),
        llm_kwargs=dict(temperature=0.01),
        benchmark_name="vifactcheck",  # Use ViFactCheck benchmark
        benchmark_kwargs=dict(variant="test"),  # test, train, or dev
        # allowed_actions=["search", "geolocate"],
        allowed_actions=["search"],
        n_samples=10,  # Start with small sample for testing
        sample_ids=None, # list of integers
        random_sampling=False,
        print_log_level="log",
        n_workers=1,  # Use 1 worker for initial testing
    )
