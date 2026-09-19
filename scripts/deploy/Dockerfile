# Dockerfile — webapi 云端部署（零依赖标准库，Python slim）
FROM python:3.11-slim
WORKDIR /app
# 只复制运行所需脚本（密钥通过运行时环境变量注入，不进镜像）
COPY webapi.py llm_router.py v15_features.py wecom_push.py ./
COPY deepseek_assistants.py ./
ENV PYTHONIOENCODING=utf-8 PYTHONUTF8=1
EXPOSE 8765
# 容器内监听 0.0.0.0；WEBAPI_TOKEN 由 -e 注入
CMD ["python", "-X", "utf-8", "webapi.py", "--port", "8765"]
