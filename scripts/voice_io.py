#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
语音交互（V15 Phase4 使用便捷性）
================================
输入（语音→指令）：
  飞书总控群发语音消息(audio) → 下载语音文件 → 飞书ASR转文字 → 走现有指令解析
  - recognize_audio_message(message_id, file_key)：完整管线，返回识别文本
  - 飞书免费版不支持 file_recognize 时，自动降级并提示用户用「飞书语音转文字发送」
输出（文字→语音，可选）：
  speak(text)：调用 Windows 自带 SAPI 朗读，零成本、不占网络、离线可用
约束：i5+16G 不跑本地 Whisper（太重），优先云端/系统自带能力。
"""
import sys, io, json, urllib.request, urllib.parse, subprocess, tempfile, os
sys.path.insert(0, '.')
from v15_features import get_token, LARK_CLI

ASR_URL = "https://open.feishu.cn/open-apis/speech_to_text/v1/speech/file_recognize"
RES_URL = "https://open.feishu.cn/open-apis/im/v1/messages/{mid}/resources/{fk}?type=file"

def _download_audio(message_id, file_key, save_path):
    """下载消息中的语音文件，返回路径"""
    tok = get_token()
    url = RES_URL.format(mid=message_id, fk=urllib.parse.quote(file_key, safe=""))
    req = urllib.request.Request(url, headers={"Authorization": "Bearer "+tok})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    with open(save_path, "wb") as f:
        f.write(data)
    return save_path

def _multipart(file_path, fmt="opus", language="zh_cn"):
    """构造 multipart/form-data"""
    boundary = "----V15VoiceBoundary7MA4YWxkTrZu0gW"
    fname = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        audio = f.read()
    def field(name, value):
        return (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n').encode("utf-8")
    body = b""
    body += field("speech", "")  # 占位，下面文件段
    body = field("language", language) + field("format", fmt) + field("speech_rate", "16000")
    body += (f'--{boundary}\r\nContent-Disposition: form-data; name="speech"; filename="{fname}"\r\n'
             f'Content-Type: audio/ogg\r\n\r\n').encode("utf-8") + audio + f"\r\n--{boundary}--\r\n".encode("utf-8")
    return body, f"multipart/form-data; boundary={boundary}"

def recognize_file(file_path, fmt="opus"):
    """调用飞书ASR识别本地音频，返回 (text, err)"""
    tok = get_token()
    body, ctype = _multipart(file_path, fmt=fmt)
    req = urllib.request.Request(ASR_URL, data=body,
        headers={"Authorization":"Bearer "+tok, "Content-Type":ctype}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read().decode()[:200]}"
    if d.get("code") == 0:
        return d.get("data", {}).get("recognizer_text", ""), None
    return None, f"code={d.get('code')} msg={d.get('msg')}"

def recognize_audio_message(message_id, file_key, fmt="opus"):
    """完整管线：消息语音 → 文本。返回 (text, status)，status: ok / unsupported / error"""
    tmp = os.path.join(tempfile.gettempdir(), f"voice_{message_id[-8:]}.opus")
    try:
        _download_audio(message_id, file_key, tmp)
    except Exception as e:
        return None, f"download_error:{e}"
    text, err = recognize_file(tmp, fmt=fmt)
    try: os.remove(tmp)
    except: pass
    if text is not None:
        return text, "ok"
    # 免费版/无权限特征：99991xxx 或 含 不支持/权限/付费
    if err and ("不支持" in err or "permission" in err.lower() or "付费" in err or "billing" in err.lower()):
        return None, "unsupported"
    return None, f"error:{err}"

def speak(text, out_path=None):
    """Windows SAPI 离线朗读；out_path 给定时存为 wav"""
    # 用 PowerShell System.Speech 合成
    safe = text.replace("'", "''").replace("\n", "。")
    if out_path:
        ps = (f"Add-Type -AssemblyName System.Speech; "
              f"$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
              f"$s.SetOutputToWaveFile('{out_path}'); $s.Speak('{safe}'); $s.Dispose();")
    else:
        ps = (f"Add-Type -AssemblyName System.Speech; "
              f"$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
              f"$s.Rate=1; $s.Speak('{safe}'); $s.Dispose();")
    try:
        r = subprocess.run(["powershell","-NoProfile","-Command",ps],
                           capture_output=True, timeout=120)
        return r.returncode == 0
    except Exception as e:
        print(f"[voice] TTS失败: {e}"); return False

def selfcheck():
    """通道自检（不需要真实语音）"""
    print("=== 语音交互通道自检 ===")
    # 1. Windows TTS
    ok = speak("语音通道测试", out_path=os.path.join(tempfile.gettempdir(),"v15_tts_test.wav"))
    wav = os.path.join(tempfile.gettempdir(),"v15_tts_test.wav")
    if ok and os.path.exists(wav):
        print(f"✅ 本地TTS可用（System.Speech），测试音频 {os.path.getsize(wav)} 字节")
    else:
        print("⚠️ 本地TTS不可用")
    print("ℹ️ 飞书云端ASR：需企业版「语音识别」权限；免费版请用飞书App「上滑语音转文字」后发送（走文本指令通道）")

if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    selfcheck()
