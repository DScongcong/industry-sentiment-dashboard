#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_data.py — 行业追踪与市场情绪研究看板 · 每日数据生成脚本

功能：
  1. 调用大模型 API（OpenAI 兼容接口），按行业追踪规则采集过去24小时资讯；
  2. 将模型输出解析、校验为前端所需的事件结构；
  3. 校验通过后覆盖写入 data/events.json；校验失败则保留旧数据并以非零码退出
     （交由 GitHub Actions 重试机制处理，保证线上看板永远拿到合法数据）。

============================= 用户需要配置的项目 =============================
所有敏感信息均通过环境变量注入（本地用 export，GitHub 用 Secrets/Variables）：

  LLM_API_KEY   (必填, Secret)  大模型 API 密钥
  LLM_BASE_URL  (可选, Variable) API 基础地址，默认 https://api.moonshot.cn/v1
  LLM_MODEL     (可选, Variable) 模型名称，默认 kimi-k2-0905-preview

注意：模型本身不具备实时联网能力时，产出质量取决于模型知识截止。
建议选用带联网检索能力的模型/接口，或在本脚本 search_news() 处接入
你自己的新闻检索 API（如财联社、新浪财经 RSS、Tavily、Serper 等），
将检索结果作为上下文喂给大模型，见下方 TODO 注释。
=============================================================================
"""

import json
import os
import sys
import shutil
from datetime import datetime, timezone, timedelta

import requests

# ---------------------------------------------------------------- 配置区 ---
BASE_URL = (os.environ.get("LLM_BASE_URL") or "https://api.moonshot.cn/v1").rstrip("/")
MODEL = os.environ.get("LLM_MODEL") or "kimi-k2-0905-preview"
API_KEY = os.environ.get("LLM_API_KEY", "").strip()  # strip: 防止粘贴密钥时带入首尾空格/换行

CST = timezone(timedelta(hours=8))                      # 中国标准时间 UTC+8
NOW = datetime.now(CST)
DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "events.json")
BACKUP_FILE = DATA_FILE + ".bak"
REQUEST_TIMEOUT = 180                                   # 秒

TRACKS = ["半导体设备", "CPO", "国产算力", "存储芯片", "恒生科技"]
EVENT_TYPES = ["政策监管", "公司公告", "行业数据", "供应链变动", "技术进展", "机构观点"]
DIRECTIONS = ["正面", "负面", "中性", "待观察"]
STRENGTHS = ["强", "中", "弱", "待验证"]
HORIZONS = ["短期", "中期", "长期"]
FACTORS = ["盈利因子", "政策因子", "流动性因子", "风险因子", "待验证"]

# ------------------------------------------------------------- Prompt 区 ---
SYSTEM_PROMPT = (
    "你是行业追踪与市场情绪研究助手。你只输出严格合法的 JSON，不输出任何其他文字。"
    "严格禁止输出买卖建议、收益预测、投资评级、涨跌判断等内容；"
    "所有标注仅为资讯属性的客观描述。"
)

USER_PROMPT_TEMPLATE = """当前中国标准时间：{now}。
请采集以下5个赛道在过去24小时内（截至上述时间）公开发布的重要资讯：
半导体设备、CPO、国产算力、存储芯片、恒生科技。

信源优先级：①监管/交易所/上市公司公告/官方新闻稿；②行业协会/政府部门/权威研究机构；
③主流财经媒体；④社交媒体仅作热度线索，不得单独作为事实依据。
同一事件多篇报道合并为一个事件，保留最权威1-3个来源；无法确认发布时间的内容不要纳入。

严格按以下 JSON 结构输出（不要输出 markdown 代码块标记，只输出 JSON 本体）：
{{
  "meta": {{
    "dataCutoff": "{now_short}（中国标准时间）",
    "timeWindow": "过去24小时",
    "generatedAt": "{now_iso}"
  }},
  "events": [
    {{
      "id": "evt-YYYYMMDD-001",
      "tracks": ["从5个赛道中选择，可多选"],
      "targets": "公司全称+简称+代码；无明确标的填 行业整体",
      "eventTypes": ["政策监管/公司公告/行业数据/供应链变动/技术进展/机构观点，可多选"],
      "sentimentFactor": "盈利因子/政策因子/流动性因子/风险因子/待验证",
      "impactDirection": "正面/负面/中性/待观察",
      "impactHorizon": "短期/中期/长期",
      "evidenceStrength": "强/中/弱/待验证",
      "coreFact": "客观事实，100字以内，不含解读",
      "marketInterpretation": "媒体/机构的分析推论；无则填空字符串",
      "rumorNote": "与传闻相关的说明；无则填空字符串",
      "publishTime": "YYYY-MM-DD",
      "sources": [{{"name": "来源名称", "time": "YYYY-MM-DD", "url": "https://..."}}]
    }}
  ],
  "rumors": [
    {{
      "id": "rum-YYYYMMDD-001",
      "track": "关联赛道",
      "content": "社媒高热度但无权威佐证的线索描述",
      "heat": "高/中/低",
      "platform": "来源平台",
      "time": "YYYY-MM-DD"
    }}
  ]
}}

要求：events 覆盖全部5个赛道（某赛道确无新增可不出现）；每条 events 的 sources 至少1个；
rumors 没有则输出空数组。所有事实必须有公开信源支撑，禁止主观演绎。"""


# ------------------------------------------------------------- 检索接口 ---
def search_news():
    """
    TODO（可选）：接入你自己的新闻检索 API，返回检索结果文本，
    作为上下文拼入 user prompt，提高时效性与可追溯性。
    示例：调用 Serper / Tavily / 自建爬虫，返回 [{title, snippet, url, date}, ...]
    未配置时返回 None，完全依赖模型自身能力。
    """
    return None


# ------------------------------------------------------------ API 调用 ----
def call_llm(prompt: str) -> str:
    """调用 OpenAI 兼容的 chat completions 接口，返回文本内容。"""
    if not API_KEY:
        raise RuntimeError("缺少环境变量 LLM_API_KEY，请先在 Secrets 中配置")

    url = f"{BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},  # 如所用模型不支持，删除此行
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    body = resp.json()
    return body["choices"][0]["message"]["content"]


def extract_json(text: str) -> dict:
    """容错解析：剥离可能的 markdown 代码块包裹后再 json.loads。"""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        # 去掉首尾 ``` 行
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return json.loads(cleaned)


# ------------------------------------------------------------ 数据校验 ----
def _one_of(value, allowed):
    return value in allowed


def validate_event(ev: dict) -> list:
    """返回该事件的错误列表；空列表表示通过。"""
    errors = []
    required = ["id", "tracks", "targets", "eventTypes", "sentimentFactor",
                "impactDirection", "impactHorizon", "evidenceStrength",
                "coreFact", "publishTime", "sources"]
    for field in required:
        if field not in ev:
            errors.append(f"缺少字段 {field}")
    if errors:
        return errors
    if not isinstance(ev["tracks"], list) or not ev["tracks"]:
        errors.append("tracks 必须为非空数组")
    if not isinstance(ev["eventTypes"], list) or not ev["eventTypes"]:
        errors.append("eventTypes 必须为非空数组")
    if not _one_of(ev["impactDirection"], DIRECTIONS):
        errors.append(f"impactDirection 非法: {ev['impactDirection']}")
    if not _one_of(ev["evidenceStrength"], STRENGTHS):
        errors.append(f"evidenceStrength 非法: {ev['evidenceStrength']}")
    if not _one_of(ev["impactHorizon"], HORIZONS):
        errors.append(f"impactHorizon 非法: {ev['impactHorizon']}")
    if not _one_of(ev["sentimentFactor"], FACTORS):
        errors.append(f"sentimentFactor 非法: {ev['sentimentFactor']}")
    if not isinstance(ev["sources"], list) or not ev["sources"]:
        errors.append("sources 必须为非空数组")
    else:
        for s in ev["sources"]:
            if not (s.get("name") and s.get("time") and s.get("url")):
                errors.append("sources 中存在缺 name/time/url 的条目")
                break
    if len(str(ev.get("coreFact", ""))) > 150:
        errors.append("coreFact 超长（>150字符）")
    return errors


def validate_data(data: dict) -> None:
    """整体校验；不通过则抛出 ValueError。"""
    if not isinstance(data, dict):
        raise ValueError("顶层结构不是 JSON 对象")
    if not isinstance(data.get("events"), list):
        raise ValueError("events 字段缺失或不是数组")
    if not isinstance(data.get("rumors", []), list):
        raise ValueError("rumors 字段不是数组")
    if not data["events"]:
        raise ValueError("events 为空，拒绝覆盖线上数据")

    all_errors = []
    for i, ev in enumerate(data["events"]):
        errs = validate_event(ev)
        for e in errs:
            all_errors.append(f"events[{i}]({ev.get('id', '?')}): {e}")
    if all_errors:
        raise ValueError("事件校验未通过：\n  " + "\n  ".join(all_errors[:20]))

    # 规范化 rumros 缺省字段
    for r in data.get("rumors", []):
        r.setdefault("track", "行业整体")
        r.setdefault("heat", "待验证")
        r.setdefault("platform", "社媒")
        r.setdefault("time", NOW.strftime("%Y-%m-%d"))


# ---------------------------------------------------------------- 主流程 ---
def main() -> int:
    print(f"[generate_data] 当前中国标准时间: {NOW.strftime('%Y-%m-%d %H:%M:%S')}")

    news_context = search_news()
    prompt = USER_PROMPT_TEMPLATE.format(
        now=NOW.strftime("%Y-%m-%d %H:%M"),
        now_short=NOW.strftime("%Y-%m-%d %H:%M"),
        now_iso=NOW.isoformat(),
    )
    if news_context:
        prompt += "\n\n以下为实时检索到的新闻线索（优先据此整理，并保留原始链接）：\n" + news_context

    # 1) 调用大模型
    print("[generate_data] 调用大模型 API ...")
    raw_text = call_llm(prompt)

    # 2) 解析 + 校验（失败则保留旧文件并退出非零，触发 Actions 重试）
    try:
        data = extract_json(raw_text)
        validate_data(data)
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        print(f"[generate_data] 输出解析/校验失败，保留现有数据文件。原因：{e}")
        return 1

    # 3) 备份旧文件后原子化写入
    data_path = os.path.abspath(DATA_FILE)
    if os.path.exists(data_path):
        shutil.copy2(data_path, BACKUP_FILE)
        print(f"[generate_data] 已备份旧数据 -> {BACKUP_FILE}")

    tmp_path = data_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp_path, data_path)  # 原子替换，避免写一半损坏

    print(f"[generate_data] 写入完成：{len(data['events'])} 条事件，"
          f"{len(data.get('rumors', []))} 条待验证线索 -> {data_path}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except requests.RequestException as e:
        print(f"[generate_data] 网络/API 调用失败：{e}")
        sys.exit(1)
    except Exception as e:  # 兜底，日志清晰
        print(f"[generate_data] 未预期错误：{type(e).__name__}: {e}")
        sys.exit(1)
