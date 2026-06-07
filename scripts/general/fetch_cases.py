"""
fetch_cases.py —— 直连北大法宝 MCP-over-HTTP 批量检索（通用类案研究）
─────────────────────────────────────────────
背景：get_case_list 单次返回 25+ 字段全要素，若经 Claude Code 的 MCP 工具通道逐次返回会灌入
对话上下文。本脚本用 .mcp.json 里同一套 endpoint + Bearer Token，以标准库 urllib 直接发
MCP JSON-RPC（Streamable HTTP），把多轮关键词轮替检索在脚本内完成、结果落盘，仅回传精简统计。
数据流向与 MCP 工具完全一致（同一法宝服务器、同一订阅 Token），只是换了调用通道。

与证券版 scripts/securities/fetch_cases.py 的区别：① title 可配置（默认空）；② **不做法院过滤**
（通用研究不限法院），仅对 --priority-courts 命中者打 `_优先` 标注；③ 保留全部 CaseGrade（双轨分流
在编码阶段做）。

用法：
    python3 scripts/general/fetch_cases.py <research_dir> --title "信息网络传播权" \
        --words "算法推荐,个性化推荐,信息流推荐,智能推荐" \
        [--priority-courts "杭州互联网法院,北京互联网法院,广州互联网法院"] [--service case]
    python3 scripts/general/fetch_cases.py <research_dir> --wordfile path  # 每行一个 fulltext 词

输出：
    <research_dir>/03_raw_cases.json   累加全字段、按 Gid 去重、每条带 _query（命中词列表）与 _优先
    stdout                             精简统计（每词命中数、去重总数、CaseGrade 分布、优先法院数）
"""

import json
import sys
import time
import urllib.request
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / ".mcp.json"
SERVICE_KEY = {
    "case": "pkulaw-case-keyword",
    "case-semantic": "pkulaw-case-semantic",
    "law": "pkulaw-law-keyword",
}


def load_endpoint(service="case"):
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    servers = cfg.get("mcpServers", cfg)
    s = servers[SERVICE_KEY[service]]
    return s["url"], s["headers"]["Authorization"]


def parse_response(body: bytes):
    """响应可能是纯 JSON 或 SSE（data: {...}）。统一抠出最后一个 JSON 对象。"""
    text = body.decode("utf-8", errors="replace")
    if text.lstrip().startswith("{"):
        return json.loads(text.lstrip())
    last = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payload = line[5:].strip()
            if payload and payload != "[DONE]":
                try:
                    last = json.loads(payload)
                except json.JSONDecodeError:
                    pass
    if last is None:
        raise ValueError(f"无法解析响应：{text[:200]}")
    return last


class MCPClient:
    def __init__(self, url, auth):
        self.url, self.auth = url, auth
        self.session_id = None
        self._rpc_id = 0

    def _headers(self):
        h = {"Authorization": self.auth, "Content-Type": "application/json",
             "Accept": "application/json, text/event-stream"}
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        return h

    def _post(self, payload, capture_session=False):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.url, data=data, headers=self._headers(), method="POST")
        with urllib.request.urlopen(req, timeout=60) as resp:
            if capture_session:
                sid = resp.headers.get("Mcp-Session-Id")
                if sid:
                    self.session_id = sid
            body = resp.read()
        return parse_response(body) if body else None

    def next_id(self):
        self._rpc_id += 1
        return self._rpc_id

    def initialize(self):
        res = self._post({"jsonrpc": "2.0", "id": self.next_id(), "method": "initialize",
                          "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                     "clientInfo": {"name": "fetch_cases_general", "version": "1.0"}}},
                         capture_session=True)
        try:
            self._post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        except Exception:
            pass
        return res

    def call_tool(self, name, arguments):
        return self._post({"jsonrpc": "2.0", "id": self.next_id(), "method": "tools/call",
                           "params": {"name": name, "arguments": arguments}})


def extract_data(rpc_result):
    """tools/call 返回 result.content[].text（JSON 字符串）→ 解析出 .Data 列表。"""
    if not rpc_result or "result" not in rpc_result:
        return None, rpc_result
    for item in rpc_result["result"].get("content", []):
        if item.get("type") == "text":
            try:
                obj = json.loads(item.get("text", ""))
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and "Data" in obj:
                return obj["Data"], obj
            return obj, obj
    return None, rpc_result


def main():
    if len(sys.argv) < 2:
        sys.exit('用法：python3 scripts/general/fetch_cases.py <research_dir> --title T --words "w1,w2"')
    rd = Path(sys.argv[1]); rd.mkdir(parents=True, exist_ok=True)

    title, words, service = "", [], "case"
    priority_courts = []
    i = 2
    while i < len(sys.argv):
        a = sys.argv[i]
        if a == "--title":
            title = sys.argv[i + 1]; i += 2
        elif a == "--words":
            words = [w.strip() for w in sys.argv[i + 1].split(",") if w.strip()]; i += 2
        elif a == "--wordfile":
            words = [l.strip() for l in Path(sys.argv[i + 1]).read_text(encoding="utf-8").splitlines()
                     if l.strip() and not l.startswith("#")]; i += 2
        elif a == "--priority-courts":
            priority_courts = [c.strip() for c in sys.argv[i + 1].split(",") if c.strip()]; i += 2
        elif a == "--service":
            service = sys.argv[i + 1]; i += 2
        else:
            i += 1
    if not words:
        words = [""]  # 允许仅靠 title 检索一轮

    url, auth = load_endpoint(service)
    cli = MCPClient(url, auth); cli.initialize()

    # 载入既有 03 累加
    raw_path = rd / "03_raw_cases.json"
    pool = {}
    if raw_path.exists():
        for c in json.loads(raw_path.read_text(encoding="utf-8")):
            g = c.get("Gid")
            if g:
                pool[g] = c

    per_word = {}
    for w in words:
        args = {}
        if title:
            args["title"] = title
        if w:
            args["fulltext"] = w
        if not args:
            continue
        try:
            data, _ = extract_data(cli.call_tool("get_case_list", args))
        except Exception as e:
            per_word[w or "(仅title)"] = f"ERROR {e}"
            continue
        data = data if isinstance(data, list) else []
        per_word[w or "(仅title)"] = len(data)
        for c in data:
            if not isinstance(c, dict):
                continue
            g = c.get("Gid")
            if not g:
                continue
            tag = w or "(仅title)"
            if g in pool:
                q = pool[g].setdefault("_query", [])
                if tag not in q:
                    q.append(tag)
            else:
                c["_query"] = [tag]
                court = str(c.get("LastInstanceCourt", ""))
                c["_优先"] = next((pc for pc in priority_courts if pc and pc in court), "")
                pool[g] = c
        time.sleep(0.3)  # 轻微限速

    cases = list(pool.values())
    raw_path.write_text(json.dumps(cases, ensure_ascii=False, indent=1), encoding="utf-8")

    # 统计
    from collections import Counter
    grade = Counter()
    for c in cases:
        cg = str(c.get("CaseGrade", ""))
        grade["普通(07)" if "07" in cg else f"其他({cg or '空'})"] += 1
    prio = sum(1 for c in cases if c.get("_优先"))
    print("== 每词命中数 ==")
    for w, n in per_word.items():
        print(f"  {w}: {n}")
    print(f"== 去重后累计 {len(cases)} 条 ==")
    print("  CaseGrade 分布:", dict(grade))
    print(f"  优先法院(命中 {','.join(priority_courts) or '—'}) 条数: {prio}")
    print(f"  写入 {raw_path}")


if __name__ == "__main__":
    main()
