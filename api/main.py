"""
云观星传 - FastAPI 后端主入口
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.routes import analyze, hypotheses, strategies, knowledge_graph, verify, parliament, outputs

# 创建 FastAPI 应用
app = FastAPI(
    title="云观星传 API",
    description="基于通义大模型的科技议题传播分析与表达系统",
    version="1.0.0",
)

# CORS 配置（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(analyze.router, prefix="/api/analyze", tags=["分析"])
app.include_router(hypotheses.router, prefix="/api/hypotheses", tags=["假设"])
app.include_router(strategies.router, prefix="/api/strategies", tags=["策略"])
app.include_router(knowledge_graph.router, prefix="/api/kg", tags=["知识图谱"])
app.include_router(verify.router, prefix="/api/verify", tags=["校验"])
app.include_router(parliament.router, prefix="/api/parliament", tags=["认知议会"])
app.include_router(outputs.router, prefix="/api/outputs", tags=["成果"])


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "message": "云观星传 API 运行正常"}


@app.get("/api/info")
async def get_info():
    """获取系统信息"""
    return {
        "name": "云观星传",
        "description": "基于通义大模型的科技议题传播分析与表达系统",
        "version": "1.0.0",
        "features": [
            "AI Scientist 范式：假设生成 - 验证 - 迭代",
            "RAG + 知识图谱双校验",
            "五维评分 + 自迭代闭环",
            "多智能体协作",
        ],
        "agents": [
            "科学理解 Agent",
            "语境分析 Agent",
            "假设生成 Agent",
            "策略转译 Agent",
            "评测迭代 Agent",
        ],
    }


# 静态文件（前端构建产物）- 必须放在所有 API 路由之后
frontend_dist = PROJECT_ROOT / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(request: Request, full_path: str):
        """SPA fallback：非 /api 路径返回 index.html"""
        file_path = frontend_dist / full_path
        if full_path and file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(frontend_dist / "index.html")


if __name__ == "__main__":
    import uvicorn
    from config.settings import API_PORT
    uvicorn.run(app, host="0.0.0.0", port=API_PORT, timeout_graceful_shutdown=2)
