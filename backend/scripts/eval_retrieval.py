#!/usr/bin/env python
"""检索质量评估脚本。

两种模式：
    1. health（默认）：无需 ground truth，跑健康自检
       - 用一组常见短句作为 query，观察 retriever 输出
       - 报告：召回数量、score 分布、source 分布、warmth 分布、延迟
       适合验证"导入完之后 retriever 能不能跑"
       且发现"所有 query 召回都一样"这种粗暴退化。

    2. eval：用户提供 ground truth JSONL，计算 Recall@K / MRR@K
       JSONL 格式（每行一条）：
           {"query": "在吗", "expected_chunk_ids": ["friend-abc", "friend-def"]}
       expected_chunk_ids 可以通过先跑一遍 /memory/search 找到。

用法：
    uv run python scripts/eval_retrieval.py            # health 模式
    uv run python scripts/eval_retrieval.py --eval dataset.jsonl
    uv run python scripts/eval_retrieval.py --queries "在吗" "晚安" "想你了"
    uv run python scripts/eval_retrieval.py --output report.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from rich.console import Console
from rich.table import Table

from xuwen.config import get_settings
from xuwen.core.errors import RetrievalError
from xuwen.core.models import RetrievalQuery, ScoredChunk
from xuwen.ingestion.embedder import EmbeddingClient
from xuwen.memory.retriever import HybridRetriever
from xuwen.memory.store import MemoryStore

console = Console()

# 健康自检默认 query 集（覆盖常见情绪场景）
DEFAULT_HEALTH_QUERIES = [
    "在吗",
    "晚安",
    "想你了",
    "今天有点累",
    "哈哈",
    "你猜怎么了",
    "嗯",
    "好的",
    "怎么了",
    "我最近不太好",
    "陪我聊会儿",
    "明天见",
]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="eval-retrieval",
        description="续温 / Afterglow 检索质量评估",
    )
    p.add_argument(
        "--eval",
        type=Path,
        default=None,
        help="可选：ground truth JSONL（{query, expected_chunk_ids}）；不提供则跑健康自检",
    )
    p.add_argument(
        "--queries",
        nargs="+",
        default=None,
        help="可选：健康自检使用的 query 列表，默认用内置 12 条常见短句",
    )
    p.add_argument(
        "--top-k",
        type=int,
        default=12,
        help="检索返回的 final_k（默认 12）",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="可选：把 markdown 报告写到此路径",
    )
    return p


async def _run_health(retriever: HybridRetriever, queries: list[str], top_k: int) -> str:
    """无 ground truth 的健康自检。"""
    results: list[tuple[str, list[ScoredChunk], float]] = []
    for q in queries:
        start = time.perf_counter()
        try:
            res = await retriever.retrieve(
                RetrievalQuery(query_text=q, final_k=top_k)
            )
        except RetrievalError as e:
            console.print(f"[red]✗[/] {q!r}：{e.message}")
            continue
        elapsed = (time.perf_counter() - start) * 1000
        results.append((q, res.fused, elapsed))

    # 控制台表格
    tbl = Table(title="健康自检：检索结果概览")
    tbl.add_column("query", overflow="fold")
    tbl.add_column("命中数", justify="right")
    tbl.add_column("top score", justify="right")
    tbl.add_column("延迟 ms", justify="right")
    tbl.add_column("来源分布")
    for q, chunks, elapsed in results:
        kinds = Counter(c.kind for c in chunks)
        kind_str = ", ".join(f"{k}={v}" for k, v in kinds.most_common())
        top = chunks[0].score if chunks else 0.0
        tbl.add_row(q, str(len(chunks)), f"{top:.4f}", f"{elapsed:.0f}", kind_str)
    console.print(tbl)

    # 退化检测：所有 query 第一名都一样？
    first_ids = [r[1][0].chunk_id if r[1] else "" for r in results]
    duplicate_rate = (
        1 - len(set(first_ids)) / max(1, len(first_ids)) if first_ids else 0
    )
    if duplicate_rate > 0.5:
        console.print(
            f"[yellow]⚠ 警告：{duplicate_rate * 100:.0f}% 的 query 召回到同一条 chunk，"
            "检索可能退化（向量库太小？embedding 出问题？）[/yellow]"
        )

    # 整体统计
    all_scores = [c.score for _, chunks, _ in results for c in chunks]
    all_warmth = [c.warmth for _, chunks, _ in results for c in chunks]
    all_kinds = Counter(c.kind for _, chunks, _ in results for c in chunks)
    all_sources = Counter(c.source for _, chunks, _ in results for c in chunks)
    avg_elapsed = (
        statistics.mean(r[2] for r in results) if results else 0
    )

    summary_tbl = Table(title="汇总")
    summary_tbl.add_column("指标")
    summary_tbl.add_column("值", justify="right")
    summary_tbl.add_row("总 query 数", str(len(results)))
    summary_tbl.add_row("失败 query 数", str(len(queries) - len(results)))
    summary_tbl.add_row("平均延迟 (ms)", f"{avg_elapsed:.0f}")
    summary_tbl.add_row(
        "score 中位数",
        f"{statistics.median(all_scores):.4f}" if all_scores else "—",
    )
    summary_tbl.add_row(
        "warmth 中位数",
        f"{statistics.median(all_warmth):.4f}" if all_warmth else "—",
    )
    summary_tbl.add_row(
        "kind 分布",
        ", ".join(f"{k}={v}" for k, v in all_kinds.most_common()) or "—",
    )
    summary_tbl.add_row(
        "source 分布",
        ", ".join(f"{k}={v}" for k, v in all_sources.most_common()) or "—",
    )
    summary_tbl.add_row("退化警告", "是" if duplicate_rate > 0.5 else "否")
    console.print(summary_tbl)

    # 返回 markdown
    md_lines: list[str] = ["# 检索健康自检报告", ""]
    md_lines.append(f"- 总 query 数：{len(results)}")
    md_lines.append(f"- 失败 query 数：{len(queries) - len(results)}")
    md_lines.append(f"- 平均延迟：{avg_elapsed:.0f} ms")
    md_lines.append(
        f"- score 中位数：{statistics.median(all_scores):.4f}"
        if all_scores
        else "- score 中位数：无数据"
    )
    md_lines.append(
        "- kind 分布："
        + (", ".join(f"{k}={v}" for k, v in all_kinds.most_common()) or "无数据"),
    )
    if duplicate_rate > 0.5:
        md_lines.append(
            f"- ⚠ 退化警告：{duplicate_rate * 100:.0f}% query 首条结果重复"
        )
    md_lines.append("")
    md_lines.append("## 每个 query 的详细召回")
    md_lines.append("")
    for q, chunks, elapsed in results:
        md_lines.append(f"### `{q}` （{elapsed:.0f} ms, {len(chunks)} 命中）")
        md_lines.append("")
        for i, c in enumerate(chunks[:5], 1):
            preview = c.text.replace("\n", " ").strip()[:80]
            md_lines.append(
                f"{i}. [{c.kind} · score={c.score:.4f} · warmth={c.warmth:.2f}] {preview}"
            )
        md_lines.append("")
    return "\n".join(md_lines)


async def _run_eval(
    retriever: HybridRetriever,
    dataset_path: Path,
    top_k: int,
) -> str:
    """带 ground truth 的评估：Recall@K / MRR@K。"""
    if not dataset_path.exists():
        console.print(f"[red]找不到数据集：{dataset_path}[/red]")
        sys.exit(1)

    items: list[dict] = []
    with dataset_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            items.append(json.loads(line))

    if not items:
        console.print("[red]数据集为空[/red]")
        sys.exit(1)

    ks = [1, 3, 5, 10, top_k]
    recall_hits: dict[int, list[int]] = {k: [] for k in ks}
    mrr_scores: list[float] = []

    detail_tbl = Table(title=f"评估（{len(items)} 条 query）")
    detail_tbl.add_column("query", overflow="fold")
    detail_tbl.add_column("期望命中", justify="right")
    detail_tbl.add_column(f"R@{top_k}", justify="right")
    detail_tbl.add_column("首条命中位次", justify="right")

    for item in items:
        query = item.get("query", "")
        expected: set[str] = set(item.get("expected_chunk_ids") or [])
        if not query or not expected:
            continue

        try:
            res = await retriever.retrieve(
                RetrievalQuery(query_text=query, final_k=max(ks))
            )
        except RetrievalError as e:
            console.print(f"[red]✗[/] {query!r}：{e.message}")
            continue

        retrieved_ids = [c.chunk_id for c in res.fused]
        for k in ks:
            top_k_set = set(retrieved_ids[:k])
            recall_hits[k].append(1 if expected & top_k_set else 0)

        # MRR：第一个命中的位次
        first_hit = next(
            (i + 1 for i, cid in enumerate(retrieved_ids) if cid in expected),
            0,
        )
        mrr_scores.append(1.0 / first_hit if first_hit > 0 else 0.0)

        top_recall = recall_hits[top_k][-1] if recall_hits[top_k] else 0
        detail_tbl.add_row(
            query[:30],
            str(len(expected)),
            "✓" if top_recall else "✗",
            str(first_hit) if first_hit > 0 else "未命中",
        )

    console.print(detail_tbl)

    # 汇总
    summary_tbl = Table(title="评估指标")
    summary_tbl.add_column("指标")
    summary_tbl.add_column("值", justify="right")
    for k in ks:
        hits = recall_hits[k]
        if hits:
            summary_tbl.add_row(
                f"Recall@{k}",
                f"{statistics.mean(hits):.3f}",
            )
    if mrr_scores:
        summary_tbl.add_row(
            f"MRR@{max(ks)}",
            f"{statistics.mean(mrr_scores):.3f}",
        )
    console.print(summary_tbl)

    md_lines: list[str] = ["# 检索评估报告", "", f"数据集：{dataset_path.name}", ""]
    for k in ks:
        hits = recall_hits[k]
        if hits:
            md_lines.append(f"- Recall@{k}: **{statistics.mean(hits):.3f}** ({sum(hits)}/{len(hits)})")
    if mrr_scores:
        md_lines.append(f"- MRR@{max(ks)}: **{statistics.mean(mrr_scores):.3f}**")
    md_lines.append("")
    return "\n".join(md_lines)


async def _main_async(args: argparse.Namespace) -> int:
    settings = get_settings()
    store = MemoryStore(settings)
    await store.connect()
    store.ensure_tables()

    stats = await store.stats()
    if stats.friend_messages == 0:
        console.print(
            "[red]向量库为空。请先运行 "
            "`uv run python -m xuwen.ingestion.cli import <json>` 导入历史聊天。[/red]"
        )
        return 1

    console.print(
        f"[bold]LanceDB[/]：friend={stats.friend_messages} "
        f"window={stats.dialogue_windows} live={stats.live_messages}"
    )

    embedder = EmbeddingClient(settings)
    retriever = HybridRetriever(settings, store=store, embedder=embedder)

    try:
        if args.eval:
            md = await _run_eval(retriever, args.eval, args.top_k)
        else:
            queries = list(args.queries) if args.queries else DEFAULT_HEALTH_QUERIES
            md = await _run_health(retriever, queries, args.top_k)
    finally:
        await embedder.aclose()

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(md, encoding="utf-8")
        console.print(f"[green]报告已保存：{args.output}[/green]")

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(_main_async(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
