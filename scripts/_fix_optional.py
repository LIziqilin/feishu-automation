with open('health_monitor.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. 修改services列表，加optional标记
old_services = '''    services = [
        ("Ollama本地模型", "http://localhost:11434/api/tags"),
        ("AnythingLLM知识库", "http://localhost:3001/"),
        ("飞书API连通性", "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"),
    ]'''

new_services = '''    # (名称, URL, 是否必需) — Ollama和AnythingLLM是可选服务，失败不告警只记录
    services = [
        ("Ollama本地模型", "http://localhost:11434/api/tags", False),
        ("AnythingLLM知识库", "http://localhost:3001/", False),
        ("飞书API连通性", "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal", True),
    ]'''

content = content.replace(old_services, new_services)

# 2. 修改循环逻辑，支持optional
old_loop = '''    for name, url in services:
        ok, msg = check_service(name, url)
        status = "正常" if ok else "异常"
        if not ok:
            all_ok = False
            failed_services.append(f"{name}({msg})")'''

new_loop = '''    for name, url, required in services:
        ok, msg = check_service(name, url)
        status = "正常" if ok else "异常"
        if not ok:
            if required:
                all_ok = False
                failed_services.append(f"{name}({msg})")
            else:
                print(f"  [可选服务异常，不告警] {name}: {msg}")'''

content = content.replace(old_loop, new_loop)

with open('health_monitor.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('OK: health_monitor.py已修复 — Ollama和AnythingLLM标记为可选服务')
