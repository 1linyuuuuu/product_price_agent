import sys
import json
import uuid
import asyncio

sys.stdout.reconfigure(encoding="utf-8")

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.runnables import RunnableConfig
from loguru import logger

from .config import settings
from .graph.workflow import build_graph
from .db.database import init_db

# 启动时初始化数据库
init_db()

app = FastAPI(title="Price Analysis Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

graph_app = build_graph()


@app.post("/analyze")
async def analyze(query: str = Query(..., min_length=2, max_length=200)):
    """非流式分析（调试用）"""
    initial_state = {
        "query": query,
        "product_name": "",
        "variants": [],
        "platforms_new": [],
        "platforms_used": [],
        "user_concern": "",
        "product_images": {},
        "price_data": {},
        "history_data": {},
        "comparison_report": "",
        "recommendation": "",
        "recommend_cards": [],
        "trend_data": {},
        "is_multi": False,
        "sub_products": [],
        "sub_results": [],
        "errors": [],
    }
    result = graph_app.invoke(initial_state)
    return {"task_id": str(uuid.uuid4()), **result}


@app.get("/analyze/stream")
async def analyze_stream(query: str = Query(..., min_length=2, max_length=200)):
    """SSE 流式分析 — connected → node_start → progress → node_complete → complete/error"""
    task_id = str(uuid.uuid4())

    def _sse_line(event: str, payload: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    async def event_generator():
        queue: asyncio.Queue[dict] = asyncio.Queue()
        config: RunnableConfig = {"configurable": {"_progress_queue": queue}}

        yield _sse_line("connected", {"task_id": task_id})

        initial_state = {
            "query": query,
            "product_name": "",
            "variants": [],
            "platforms_new": [],
            "platforms_used": [],
            "user_concern": "",
            "product_images": {},
            "price_data": {},
            "history_data": {},
            "comparison_report": "",
            "recommendation": "",
            "recommend_cards": [],
            "trend_data": {},
            "is_multi": False,
            "sub_products": [],
            "sub_results": [],
            "errors": [],
        }

        async def run_graph():
            accumulated: dict = {}
            try:
                async for chunk in graph_app.astream(initial_state, config, stream_mode="updates"):
                    node_name = list(chunk.keys())[0] if chunk else "unknown"
                    node_data = chunk.get(node_name, {})
                    # 按 Annotated reducer 规则合并（stream_mode="updates" 绕过归约器）
                    for key, value in node_data.items():
                        if key in ("errors", "recommend_cards"):
                            accumulated[key] = accumulated.get(key, []) + value
                        elif key in ("price_data", "history_data"):
                            accumulated[key] = {**accumulated.get(key, {}), **value}
                        else:
                            accumulated[key] = value
                    await queue.put({"event": "node_complete", "data": {"node": node_name}})
                await queue.put({
                    "event": "complete",
                    "data": {
                        "task_id": task_id,
                        "product_images": accumulated.get("product_images", {}),
                        "price_table": accumulated.get("price_data", {}),
                        "trend_data": accumulated.get("trend_data", {}),
                        "comparison_report": accumulated.get("comparison_report", ""),
                        "recommendation": accumulated.get("recommendation", ""),
                        "recommend_cards": accumulated.get("recommend_cards", []),
                        "errors": accumulated.get("errors", []),
                    }
                })
            except Exception as e:
                logger.error(f"Stream error: {e}")
                await queue.put({"event": "error", "data": {"message": str(e)}})

        asyncio.create_task(run_graph())

        while True:
            data = await queue.get()
            yield _sse_line(data["event"], data["data"])
            if data["event"] in ("complete", "error"):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting server on {settings.HOST}:{settings.PORT}")
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)
