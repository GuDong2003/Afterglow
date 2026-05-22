"""把 PersonaReport 渲染为 markdown 卡片，并提供加载/保存接口。

卡片会直接喂给 prompt 模板，因此要保持简洁、贴近自然语言、不带统计学黑话。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from xuwen.persona.analyzer import (
    DialogueSample,
    PersonaReport,
    TermStat,
    report_to_dict,
)


def render_persona_card(report: PersonaReport) -> str:
    """根据画像统计渲染人类可读的 markdown 卡片。

    输出会被嵌入 prompt 模板的 `{{ persona_card }}` 变量。
    """
    lines: list[str] = []
    name = report.friend_name or "TA"

    lines.append(f"# {name} 的画像")
    lines.append("")
    lines.append(
        f"基于 {report.total_messages} 条历史聊天，其中 {name} 发出 "
        f"{report.friend_message_count} 条。"
    )
    lines.append("")
    lines.append(
        "> 这是长期统计画像，只能作为语气参考；具体回复优先参考当前生活状态、"
        "关系记忆和本轮检索到的真实回复样本。不要凭画像发明当天事实、emoji、"
        "亲密动作或现实生活经历。"
    )
    lines.append("")

    # 语言节奏
    lines.append("## 语言节奏")
    short = report.length.short_ratio
    long_ = report.length.long_ratio
    rhythm: list[str] = []
    if short > 0.6:
        rhythm.append("以短句为主，习惯连发几条")
    elif short > 0.4:
        rhythm.append("偏短句")
    if long_ > 0.2:
        rhythm.append("偶尔会长篇展开")
    if not rhythm:
        rhythm.append("句长比较均衡")
    rhythm.append(
        f"平均每条 {report.length.mean:.1f} 字（中位数 {report.length.median:.1f} 字）"
    )
    lines.append("- " + "；".join(rhythm))
    lines.append("")

    # 标点习惯
    lines.append("## 标点与情绪表达")
    punct_bits: list[str] = []
    if report.punctuation.no_punct_ratio > 0.4:
        punct_bits.append(f"约 {int(report.punctuation.no_punct_ratio * 100)}% 的消息没有标点")
    if report.punctuation.question_ratio > 0.2:
        punct_bits.append("爱用问号追问")
    if report.punctuation.exclaim_ratio > 0.2:
        punct_bits.append("感叹号比较多，情绪外放")
    if report.punctuation.ellipsis_ratio > 0.1:
        punct_bits.append("习惯用省略号表达停顿或欲言又止")
    if report.media.emoji_per_message > 0.3:
        punct_bits.append("会用 emoji")
    if not punct_bits:
        punct_bits.append("标点使用比较克制")
    lines.append("- " + "；".join(punct_bits))
    lines.append("")

    # 媒体
    if report.media.placeholder_ratio > 0.05:
        media_bits: list[str] = []
        if report.media.image_ratio > 0.03:
            media_bits.append(
                f"图片占约 {int(report.media.image_ratio * 100)}%（会用图片表达反应；"
                "模型不能直接输出 [图片] 占位符）"
            )
        if report.media.voice_ratio > 0.02:
            media_bits.append("偶尔发语音")
        if media_bits:
            lines.append("## 媒体使用习惯")
            for bit in media_bits:
                lines.append(f"- {bit}")
            lines.append("")

    # 口头禅 / 高频短语
    phrases = [p for p in report.top_phrases if len(p.term) >= 2][:12]
    if phrases:
        lines.append("## 常用短语 / 口头禅")
        lines.append("> 学习这些词组的使用语境，但不要逐字复读。")
        lines.append("")
        for p in phrases:
            lines.append(f"- 「{p.term}」(出现 {p.count} 次)")
        lines.append("")

    # 高频词
    terms = report.top_terms[:20]
    if terms:
        lines.append("## 高频词（参考）")
        lines.append(_format_terms(terms))
        lines.append("")

    # 样本
    if report.samples:
        lines.append("## 典型对话样本")
        lines.append(f"> 真实历史中 {name} 是如何回应的；写新回复时参考其语气，不要照抄。")
        lines.append("")
        for s in report.samples[:8]:
            lines.append(_format_sample(s, report.self_name or "我", name))
            lines.append("")

    lines.append(f"---\n*生成于 {datetime.now(UTC).isoformat(timespec='seconds')}*")
    return "\n".join(lines).strip() + "\n"


def save_persona_card(markdown: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")


def load_persona_card(path: Path) -> str:
    """加载已生成的卡片。文件不存在时返回空字符串（让 prompt 模板自行兜底）。"""
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def save_persona_report(report: PersonaReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report_to_dict(report), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# 内部
# ---------------------------------------------------------------------------


def _format_terms(terms: list[TermStat]) -> str:
    return "、".join(f"{t.term}({t.count})" for t in terms)


def _format_sample(s: DialogueSample, self_name: str, friend_name: str) -> str:
    user = s.user_text[:80]
    friend = s.friend_text[:120]
    return f"{self_name}：{user}\n{friend_name}：{friend}"
