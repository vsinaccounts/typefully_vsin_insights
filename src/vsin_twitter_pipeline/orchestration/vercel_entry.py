from vsin_twitter_pipeline.orchestration.main import run


def handler(request):  # noqa: ANN001
    summary = run()
    return {"ok": True, "summary": summary}
