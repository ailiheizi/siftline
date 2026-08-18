#!/usr/bin/env python3
"""lint_draft.py — evidence-integrity linter for siftline-research drafts.

Reads a draft from --file PATH or stdin and reports coded, line-numbered
violations of the siftline-research integrity rules. Exits 1 when any error is
found, prints PASS and exits 0 when clean. Exits 2 with MAX_CHARS_REQUIRED when
a structured profile is missing or given both length-contract options.

Checks
------
MAX_CHARS           whole document exceeds --max-chars (checked only when given)
MARGIN_EXCEEDED     whole document exceeds (100-P)% of --max-chars with a
                    positive --min-margin-pct (default 8), so the final draft
                    keeps at least P% headroom below the cap
CODE_VERIFIED_SCOPE a code-verified / 已代码核验 claim does not name the
                    exercised surface (a focused command, test, or source file)
HTTPS_REQUIRED      http:// URL present; drafts must cite over https://
CITATION_HTTP       bare citation domain without an https:// scheme
CAUSAL_UNTAGGED     success/adoption attribution phrase with no
                    observed/documented/inferred/unverified state
STATE_SURFACE       observed playable-surface claim citing only build/typecheck/unit
                    tests with no surface-exercised evidence
LEVEL5_MARKET       level-5 (attention) paragraph using demand/market-size language
ATTENTION_OVERREACH weak-evidence cap (attention-only, level-5, Worldloom
                    需求强度只能封顶为 attention + 显式子机制请求, single
                    level-4 request) draft asserts a non-negated market claim
                    (机制吸引力中等/高, 主流采纳, 竞争基线, 痛点在生态中真实存在,
                    玩家痴迷), or asserts a 成功/成功近邻/成功邻居/successful
                    neighbor label, or successful-neighbor wording outside a cap
                    lacks positive non-negated direct adoption/outcome evidence
UNTAGGED_THRESHOLD  numeric or Chinese-number-word criterion in a test/reversal
                    section without an immediately following [quoted threshold — ...]
                    or [proposed test threshold] tag
FINAL_STRUCTURE     profile draft below its minimum length or missing a required
                    bilingual structural marker (audit/discovery/coverage only)
BOUNDED_GAP         ecosystem-wide absence phrase (生态缺口/生态空白/竞争真空/
                    市场空白/无人做/real gap/no competitor/...) without bounded
                    channels/platforms, query or vocabulary, and retrieval date in
                    the same paragraph
COVERAGE_DENOMINATOR  coverage profile lacks a literal coverage_by_source: block,
                     or its rows are missing/malformed/non-summing, or an unscorable
                     row has no reason, or a paragraph locally associates an
                     omitted/unextracted/unscorable label (遗漏/未提取/未评分) with a
                     literal .md source that has no matching source= row by path or
                     basename, or nonblank text follows the block rows (the block
                     must end the final output)
SIFTLINE_OPERATIONS  structured draft mentioning siftline/query-id/query_id/
                     provider_calls that omits any of the exact fields
                     machine_attempts, unledgered_attempts, effective_attempts,
                     provider_calls, budget with a numeric value
UNBALANCED_DELIMITER ASCII/Chinese parentheses or brackets unbalanced after masking
                     code fences, inline code, and URLs
FINAL_WRAPPER        audit/discovery/coverage final answer whose first nonblank
                     line is not a Markdown heading (prefix narration fails)

Profiles (--profile)
--------------------
basic       no structural requirements (default)
audit       >=350 chars; conclusion, evidence state, source/command markers
discovery   >=650 chars; conclusion, findings/evidence, boundary/counterevidence/
            uncertainty, and next test/check/minimum observation markers
coverage    >=800 chars; all discovery markers plus coverage-source/checklist and
            matrix markers

Length contract
---------------
For audit, discovery and coverage, the CLI requires exactly one length-contract
option: --max-chars N or --no-max-chars. Giving neither or giving both prints
MAX_CHARS_REQUIRED to stderr and exits 2. basic and --self-test are exempt.
--max-chars counts Unicode code points, so Chinese character caps are passed
as natural char counts.

When --max-chars N is given on a structured profile, --min-margin-pct P
(default 8) additionally requires the draft to stay at or below
N x (100-P)/100 chars; exceeding it is MARGIN_EXCEEDED. This keeps at least
P% headroom below the cap so the emitted answer is not pinned to the ceiling.
Explicitly passing --min-margin-pct without --max-chars on a structured
profile prints MARGIN_REQUIRES_MAX_CHARS to stderr and exits 2.

On a clean draft the output is "PASS threshold_unlabeled=0". With --emit, a clean
draft echoes the input exactly instead of printing the PASS line.

Only the Python standard library is used.
"""

import argparse
import io
import os
import re
import sys
import tempfile

CODE_MAX_CHARS = "MAX_CHARS"
CODE_MARGIN = "MARGIN_EXCEEDED"
CODE_MARGIN_REQUIRED = "MARGIN_REQUIRES_MAX_CHARS"
CODE_VERIFIED = "CODE_VERIFIED_SCOPE"
CODE_CITATION = "CITATION_HTTP"
CODE_CAUSAL = "CAUSAL_UNTAGGED"
CODE_STATE_SURFACE = "STATE_SURFACE"
CODE_LEVEL5 = "LEVEL5_MARKET"
CODE_THRESHOLD = "UNTAGGED_THRESHOLD"
CODE_FINAL = "FINAL_STRUCTURE"
CODE_GAP = "BOUNDED_GAP"
CODE_COVERAGE = "COVERAGE_DENOMINATOR"
CODE_MAX_CHARS_REQUIRED = "MAX_CHARS_REQUIRED"
CODE_HTTPS = "HTTPS_REQUIRED"
CODE_OVERREACH = "ATTENTION_OVERREACH"
CODE_SIFT = "SIFTLINE_OPERATIONS"
CODE_DELIM = "UNBALANCED_DELIMITER"
CODE_WRAPPER = "FINAL_WRAPPER"

CONTRACT_PROFILES = ("audit", "discovery", "coverage")

TAG_PLACEHOLDER = "\u00abTAG\u00bb"

QUOTED_TAG_RE = re.compile(r"\[quoted threshold \u2014[^\]]*\]")
PROPOSED_TAG_RE = re.compile(r"\[proposed test threshold\]")
FENCE_RE = re.compile(r"^\s*(```+|~~~+)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
INLINE_CODE_RE = re.compile(r"`[^`]*`")
BRACKET_RE = re.compile(r"\[[^\]]*\]")
DATE_RE = re.compile(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b")
YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
NUMERAL_RE = re.compile(r"\d[\d,，\.]*")

SCHEMED_URL_RE = re.compile(r"(?:https?|ftp)://[^\s<>\"'\]\)]+")
DOMAIN_RE = re.compile(r"(?<![\w@/:.])([a-zA-Z0-9][a-zA-Z0-9-]*\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})?)(?![\w-])")
HTTP_URL_RE = re.compile(r"http://[^\s<>\x22\x27\]\)\},;，。；、）】！？?!]+")

CAUSAL_RE = re.compile(
    r"\b(?:its\s+)?success\s+(?:came|comes|resulted|result|is|was)\s+"
    r"(?:from|due\s+to|attributed\s+to|owing\s+to)"
    r"|\bsuccess\s+is\s+because"
    r"|\b(?:is|was|been)\s+attributed\s+to"
    r"|\battributed\s+its\s+success\s+to"
    r"|\b(?:drove|drives|boosted|fueled|propelled)\s+(?:its\s+)?"
    r"(?:adoption|success|growth)"
    r"|\b(?:led|leads)\s+to\s+(?:its\s+)?(?:success|adoption|growth)"
    r"|\bsucceed(?:s|ed)?\s+(?:due\s+to|because\s+of|thanks\s+to|"
    r"owing\s+to|as\s+a\s+result\s+of)"
    r"|\b(?:is|was)\s+successful\s+because"
    r"|成功\s*(?:是)?(?:因为|由于)|成功.*?(?:归因于|得益于|源于|因为|由于)"
    r"|(?:成功|采用|增长).*?(?:因为|由于|归因于|得益于|源于)"
    r"|归因于|得益于|成功源于"
    r"|(?:驱动|推动|导致).*?(?:成功|采用|增长|流行|火爆)",
    re.IGNORECASE,
)
EVIDENCE_RE = re.compile(
    r"\b(?:observed|documented|inferred|unverified|code-verified)\b|"
    r"未验证|已观察|已文档化|推断|已代码核验",
    re.IGNORECASE,
)
CODE_VERIFIED_RE = re.compile(r"\bcode-verified\b|已代码核验", re.IGNORECASE)
# A code-verified claim must name the exercised surface: a focused command, a
# test run, or a concrete source file. build/typecheck/bundle are surfaces but
# only for what they observe — never for playability, availability, or UX.
SURFACE_MARKER_RE = re.compile(
    r"\b(?:pytest|go\s+test|npm\s+test|npm\s+run\s+\w+|npx\s+\w+|"
    r"vitest|tsc(?:\s|$)|python\s+-m|flake8|ruff(?:\s|$)|"
    r"validate-content|node\s+--(?:import|test)|go\s+vet)\b"
    r"|\w+\.(?:py|ts|tsx|js|go|rs)\b"
    r"|\w+\.test\.\w+\b"
    r"|focused\s+test\b"
    r"|已运行\s*[^\s，。]{0,12}测试|实际运行\s*[^\s，。]{0,12}测试"
    r"|已读\s*[\w./-]+\.(?:py|ts|tsx|go|rs)\b",
    re.IGNORECASE,
)
OBSERVED_RE = re.compile(r"\bobserved\b|观察到|已观察", re.IGNORECASE)
PLAYABLE_RE = re.compile(r"\b(?:playable|fun)\b|可玩|真正可玩|实际玩家循环|好玩")
TEST_CITED_RE = re.compile(
    r"\b(?:build|builds|bundle|bundles|typecheck|type-checks?|unit\s+test|"
    r"unit\s+tests|test\s+suite|test\s+suites|tests?\s+passed|tests?\s+pass)\b"
    r"|构建|编译|单元测试|类型检查|测试通过|测试套件",
    re.IGNORECASE,
)
SURFACE_EXERCISED_RE = re.compile(
    r"实际运行游戏|浏览器会话|play\s+session|亲自运行游戏|launched\s+and\s+exercised|"
    r"exercised\s+the\s+(?:game|browser|ui|surface)|ran\s+the\s+game|"
    r"ran\s+the\s+browser|played\s+through|实际游玩|试玩|亲手玩过",
    re.IGNORECASE,
)
# A pure evidence-state legend/taxonomy line (labels only, no claim) is exempt
# from the CODE_VERIFIED_SCOPE surface requirement; declaring the state taxonomy
# is not the same as asserting a code-verified claim.
EVIDENCE_LEGEND_RE = re.compile(
    r"^\s*(?:(?:evidence(?:\s+states?)?|states?|status|labels?|taxonomy|"
    r"证据(?:状态|标记)?|状态)\s*[:：\-]?\s*)?"
    r"(?:observed|documented|inferred|unverified|code-verified|"
    r"已观察|已文档化|推断|未验证|已代码核验)"
    r"(?:\s*[,，、;；]\s*(?:observed|documented|inferred|unverified|code-verified|"
    r"已观察|已文档化|推断|未验证|已代码核验))*"
    r"\s*[.。]?\s*$",
    re.IGNORECASE,
)
# build/typecheck surfaces observe only build/typecheck; a code-verified
# playability/availability/UX claim citing only these is a STATE_SURFACE error.
BUILD_TYPECHECK_RE = re.compile(
    r"\b(?:build|builds|built|bundle|bundles|bundled|typecheck|type-check|"
    r"type-checks?|tsc|compil(?:e|es|ed|ing))\b"
    r"|npm\s+run\s+(?:build|typecheck|type-check)\b"
    r"|构建|编译|类型检查|编译通过|构建通过",
    re.IGNORECASE,
)
# Focused tests or concrete source-file reads legitimately code-verify their own
# surface. This is SURFACE_MARKER_RE minus build/typecheck-only surfaces.
FOCUSED_SURFACE_RE = re.compile(
    r"\b(?:pytest|go\s+test|npm\s+test|npm\s+run\s+test(?::\w+)?|vitest|"
    r"python\s+-m|flake8|ruff(?:\s|$)|validate-content|"
    r"node\s+--(?:import|test)|go\s+vet)\b"
    r"|\w+\.(?:py|ts|tsx|js|go|rs)\b"
    r"|\w+\.test\.\w+\b"
    r"|focused\s+test\b"
    r"|已运行\s*[^\s，。]{0,12}测试|实际运行\s*[^\s，。]{0,12}测试"
    r"|已读\s*[\w./-]+\.(?:py|ts|tsx|go|rs)\b",
    re.IGNORECASE,
)
# Surfaces a build/typecheck can never prove: playability, availability, UX.
SURFACE_CLAIM_RE = re.compile(
    r"\b(?:playability|playable|fun|availability|available|usability|usable|"
    r"user[- ]facing|ux)\b"
    r"|可玩|真正可玩|实际玩家循环|好玩|可用|可运行|可用性|用户体验",
    re.IGNORECASE,
)

LEVEL5_RE = re.compile(
    r"\b(?:star[s]?|likes?|views?|upvotes?|points?|followers?|subscribers?|"
    r"ratings?|sales\s+rank|concurrents?|concurrent\s+(?:players?|users?|"
    r"counts?)?|watch\s+counts?|downloads?|trending|hype|buzz|hn\s+points|"
    r"level-5|attention|review(?:s)?)\b"
    r"|获赞|点赞|关注|浏览量|观看|注意力|评论|评测",
    re.IGNORECASE,
)
MARKET_RE = re.compile(
    r"\b(?:strong|broad|large|small|real|validated|proves?|huge|big)\s+"
    r"(?:demand|market|audience)\b|proves?\s+demand|proves?\s+real\s+audience|"
    r"strong\s+demand|证明需求|有真实受众|有吸引力|证明诉求|loop\s+成立|"
    r"循环成立|validated|规模大|规模小|市场大|市场小|大市场|小市场|"
    r"blue\s+ocean|市场空白|无人做|market\s+size|market-size|受众巨大|"
    r"小众信号|强需求",
    re.IGNORECASE,
)
NEGATION_RE = re.compile(
    r"(?:not|no|cannot|can't|doesn't|don't|won't|never|没有|并未|尚未|未曾|未被|未获|"
    r"不能|无法|并不|不会)",
    re.IGNORECASE,
)

GLOBAL_CAP_RE = re.compile(
    r"all\s+external\s+evidence\s+is\s+(?:level-?5|attention)"
    r"|all\s+evidence\s+is\s+(?:level-?5|attention)"
    r"|all\s+external\s+evidence\s+is\s+only\s+(?:level-?5|attention)"
    r"|all\s+evidence\s+is\s+only\s+(?:level-?5|attention)"
    r"|attention(?:-|\s)only"
    r"|level-?5\s+only"
    r"|仅.{0,10}(?:注意力|5\s*级|level-?5)"
    r"|所有外部证据.{0,12}(?:5\s*级|level-?5|注意力)"
    r"|全部外部证据.{0,12}(?:5\s*级|level-?5|注意力)"
    r"|证据仅.{0,10}(?:注意力|5\s*级|level-?5)"
    r"|全部证据.{0,10}注意力"
    r"|需求强度\s*(?:只能|最多|至多)?\s*封顶\s*[为在]?\s*(?:attention|level-?4)"
    r"|需求强度.{0,20}显式子机制请求"
    r"|证据\s*(?:仅|只能|最多|至多)?\s*封顶\s*[为在]?\s*(?:attention|level-?4)"
    r"|attention\s*封顶"
    r"|封顶为\s*attention"
    r"|单\s*(?:个|条|次)?\s*level-?4\s*请求"
    r"|single\s+level-?4\s+request"
    r"|capped\s+at\s+(?:attention|level-?4)"
    r"|evidence\s+.{0,12}capped\s+at\s+attention",
    re.IGNORECASE,
)
MARKET_OVERREACH_RE = re.compile(
    r"机制吸引力\s*(?:中等|较高|极高|偏高|高)"
    r"|获主流采纳|获得主流采纳|赢得主流采纳"
    r"|竞争基线"
    r"|痛点在生态中真实存在"
    r"|玩家痴迷"
)
SUCCESS_NEIGHBOR_RE = re.compile(
    r"成功.{0,20}(?:近邻|邻居)|successful.{0,20}neighbou?rs?",
    re.IGNORECASE,
)
MD_EMPH_RE = re.compile(r"\*{1,2}|_{1,2}|~{2}")
ADOPTION_RE = re.compile(
    r"已采用|被采用|明确采用|直接采用|已落地|已收购|被收购|已部署|已购买|"
    r"用户已(?:付费|购买|使用)|付费用户|购买记录|营收|收入数据|销售数据|"
    r"adopted|direct\s+adoption|paying\s+(?:users?|customers?)|revenue|"
    r"sales\s+data|outcomes?",
    re.IGNORECASE,
)

GAP_RE = re.compile(
    r"全链路生态缺口|生态缺口|生态空白|竞争真空|市场空白|无人做|"
    r"\breal\s+gap\b|\bclear\s+whitespace\b|under-occupied\s+niche|"
    r"\bno\s+competitor\b|ecosystem\s+has\s+no\s+equivalent",
    re.IGNORECASE,
)
GAP_CHANNEL_RE = re.compile(
    r"\b(?:github|steam|itch(?:\.io)?|app\s*store|google\s*play|product\s*hunt|"
    r"hacker\s*news|reddit|youtube|twitter|discord|npm|pypi|curseforge|moddb|"
    r"telegram|forum|subreddit|newsletter)\b"
    r"|平台|渠道|\bchannels?\b|\bplatforms?\b",
    re.IGNORECASE,
)
GAP_QUERY_RE = re.compile(
    r"\bquery\b|\bqueries\b|\bsearch\s+term|\bkeywords?\b|\bvocabulary\b|词表|"
    r"搜索|检索|关键词|检索词|搜索词",
    re.IGNORECASE,
)
GAP_DATE_RE = re.compile(
    r"\bretrieved\s+(?:on\s+)?\d{4}[-/]\d{1,2}[-/]\d{1,2}"
    r"|\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+retrieved"
    r"|\bretrieved_at=\d{4}[-/]\d{1,2}[-/]\d{1,2}"
    r"|检索于\s*\d{4}[-/]\d{1,2}[-/]\d{1,2}"
    r"|检索\s*\d{4}[-/]\d{1,2}[-/]\d{1,2}"
    r"|检索日期[:：]?\s*\d{4}[-/]\d{1,2}[-/]\d{1,2}",
    re.IGNORECASE,
)
VERSION_ID_RE = re.compile(r"(?<![\w.])[PpVv]\d+(?:\.\d+)*(?![\w-])")

SIFT_TRIGGER_RE = re.compile(r"\bsiftline\b|query[-_]id|provider_calls", re.IGNORECASE)
SIFT_FIELDS = (
    ("machine_attempts", re.compile(r"\bmachine_attempts\s*[:=]\s*\d+\b")),
    ("unledgered_attempts", re.compile(r"\bunledgered_attempts\s*[:=]\s*\d+\b")),
    ("effective_attempts", re.compile(r"\beffective_attempts\s*[:=]\s*\d+\b")),
    ("provider_calls", re.compile(r"\bprovider_calls\s*[:=]\s*\d+\b")),
    ("budget", re.compile(r"\bbudget\s*[:=]\s*\d+\b")),
)
DELIM_PAIRS = (
    ("ASCII parens", "(", ")"),
    ("Chinese parens", "\uff08", "\uff09"),
    ("ASCII brackets", "[", "]"),
    ("Chinese brackets", "\u3010", "\u3011"),
)
REF_DEF_RE = re.compile(r"\[[^\]]*\]\s*:\s*\S+")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->")
EMOTICON_RE = re.compile(r"[:;][-~]?[()DdPpOo0]")
LIST_ITEM_CLOSE_RE = re.compile(r"(?m)^\s*\d+\s*\)")
DELIM_URL_RE = re.compile(r"(?:https?|ftp)://[^\s<>\"'\]]+")

SECTION_RE = re.compile(
    r"test|reversal|测试|反转|最小观察|最可能推翻|推翻|minimum\s+observation",
    re.IGNORECASE,
)

UNIT_TOKEN_RE = re.compile(r"\s*(?:[a-zA-Z\u4e00-\u9fff%％×]+\s*){0,2}")
RANGE_RE = re.compile(r"\s*[-~～–—到至]\s*\d")
SOURCE_REF_RE = re.compile(r"\b[a-zA-Z][\w.-]*/\d+(?:[\w./-]*)?\b|§\s*\d+")
CN_NUM_RE = re.compile(
    r"[一二三四五六七八九十两]+(?=[个位人天周月年秒分小阶轮名次条篇份张倍点项局盘关级%])"
)
FILE_EXTENSIONS = {"md", "txt", "toml", "yaml", "yml", "json", "py", "js", "ts"}

CONCLUSION_RE = re.compile(r"\bconclusion\b|结论", re.IGNORECASE)
FINDINGS_RE = re.compile(
    r"\bfinding|findings\b|\bevidence\b|发现|证据", re.IGNORECASE
)
BOUNDARY_RE = re.compile(
    r"\bboundary|boundaries\b|counterevidence|counter-evidence|反例|反证|边界|"
    r"\buncertain|uncertainty\b|不确定|不确定性|风险|risk|limitations?|局限",
    re.IGNORECASE,
)
NEXT_STEP_RE = re.compile(
    r"\bnext\s+(?:test|check|step|observation|experiment)\b|下一步|待验证|待测|"
    r"minimum\s+observation|最小观察|next\s+check",
    re.IGNORECASE,
)
SOURCE_COMMAND_RE = re.compile(r"\bsource\b|来源|\bcommand\b|命令", re.IGNORECASE)
COVERAGE_RE = re.compile(
    r"\bcoverage\b|覆盖率|checklist|清单|覆盖源|cover\s+source", re.IGNORECASE
)
MATRIX_RE = re.compile(r"\bmatrix\b|矩阵", re.IGNORECASE)

PROFILES = ("basic", "audit", "discovery", "coverage")

DISCOVERY_MARKERS = [
    ("conclusion", CONCLUSION_RE),
    ("findings/evidence", FINDINGS_RE),
    ("boundary/counterevidence/uncertainty", BOUNDARY_RE),
    ("next test/check/minimum observation", NEXT_STEP_RE),
]
FINAL_SPECS = {
    "audit": {
        "min_chars": 350,
        "markers": [
            ("conclusion", CONCLUSION_RE),
            ("evidence state", EVIDENCE_RE),
            ("source/command", SOURCE_COMMAND_RE),
        ],
    },
    "discovery": {"min_chars": 650, "markers": DISCOVERY_MARKERS},
    "coverage": {
        "min_chars": 800,
        "markers": DISCOVERY_MARKERS
        + [("coverage-source/checklist", COVERAGE_RE), ("matrix", MATRIX_RE)],
    },
}

COVERAGE_BLOCK_RE = re.compile(r"coverage_by_source:")
COVERAGE_ROW_RE = re.compile(
    r"^\s*(?:-\s+)?source=([^\s=]+)\s+"
    r"total=(\d+)\s+implemented=(\d+)\s+partial=(\d+)\s+"
    r"planned=(\d+)\s+absent=(\d+)\s+unmapped=(\d+)\s*$"
)
UNSCORABLE_ROW_RE = re.compile(
    r"^\s*(?:-\s+)?source=([^\s=]+)\s+score=unscorable\s+reason=(\S.*)\s*$"
)
UNSCORABLE_PREFIX_RE = re.compile(r"^\s*(?:-\s+)?source=[^\s=]+\s+score=unscorable\b")

MD_LITERAL_RE = re.compile(r"[\w./-]+\.md\b")
COVERAGE_STATUS_RE = re.compile(
    r"\bomitted\b|\bunextracted\b|\bunscorable\b|遗漏|未提取|未评分",
    re.IGNORECASE,
)
CLAUSE_RE = re.compile(r"[，。；,;？?！!]")
STATUS_LABEL_TAIL_RE = re.compile(
    r"(?:omitted|unextracted|unscorable|遗漏|未提取|未评分)[\s:：，,]*$"
)


def _is_omitted_source(line, m):
    """True when the .md literal at m is locally associated with an omitted/
    unextracted/unscorable label: a status label immediately followed by the
    .md, or the .md followed within a small window and the same clause by a
    status word."""
    before = line[max(0, m.start() - 24):m.start()]
    if STATUS_LABEL_TAIL_RE.search(before):
        return True
    seg_end = m.end() + 24
    if seg_end > len(line):
        seg_end = len(line)
    cm = CLAUSE_RE.search(line, m.end())
    if cm and cm.start() < seg_end:
        seg_end = cm.start()
    return bool(COVERAGE_STATUS_RE.search(line[m.end():seg_end]))


def _mask(text, regex, replacement=""):
    return regex.sub(replacement, text)


def _mask_with(text, regex, replacement):
    return regex.sub(lambda m: replacement * len(m.group(0)), text)


def _line_clean(line):
    line = _mask_with(line, SCHEMED_URL_RE, " ")
    line = _mask_with(line, INLINE_CODE_RE, " ")
    line = _mask_with(line, QUOTED_TAG_RE, " ")
    line = _mask_with(line, PROPOSED_TAG_RE, " ")
    line = _mask_with(line, BRACKET_RE, " ")
    line = _mask_with(line, DATE_RE, " ")
    line = _mask_with(line, YEAR_RE, " ")
    return line


def _tag_follows(tail, pos):
    m = UNIT_TOKEN_RE.match(tail, pos)
    end = m.end() if m else pos
    rest = tail[end:]
    if rest.startswith(TAG_PLACEHOLDER):
        return True
    return rest.startswith("[quoted threshold \u2014") or rest.startswith("[proposed test threshold]")


def _is_range_start(tail, pos):
    return bool(RANGE_RE.match(tail, pos))


def _is_list_marker(tagged, m):
    if tagged[:m.start()].strip():
        return False
    if m.group(0).endswith("."):
        return True
    return tagged[m.end():].startswith((")", "、"))


def _is_local_filename(text, m):
    last = m.group(1).rsplit(".", 1)[-1].lower()
    if last not in FILE_EXTENSIONS:
        return False
    return not text[m.end():].startswith("/")


def _strip_md_emphasis(text):
    return MD_EMPH_RE.sub("", text)


def _has_positive_adoption(joined):
    for m in ADOPTION_RE.finditer(joined):
        start = max(0, m.start() - 12)
        if NEGATION_RE.search(joined[start:m.start() + 1]):
            continue
        return True
    return False


def _line_with_tags(line):
    masked = _mask_with(line, QUOTED_TAG_RE, TAG_PLACEHOLDER)
    masked = _mask_with(masked, PROPOSED_TAG_RE, TAG_PLACEHOLDER)
    masked = _mask_with(masked, VERSION_ID_RE, " ")
    masked = _mask_with(masked, SCHEMED_URL_RE, " ")
    masked = _mask_with(masked, SOURCE_REF_RE, " ")
    masked = _mask_with(masked, INLINE_CODE_RE, " ")
    masked = _mask_with(masked, BRACKET_RE, " ")
    masked = _mask_with(masked, DATE_RE, " ")
    masked = _mask_with(masked, YEAR_RE, " ")
    return masked


def _negated_before(text, match_start):
    start = max(0, match_start - 8)
    return bool(NEGATION_RE.search(text[start:match_start]))


def _final_structure_errors(profile, text):
    if profile == "basic" or profile not in FINAL_SPECS:
        return []
    spec = FINAL_SPECS[profile]
    total = len(text)
    if total < spec["min_chars"]:
        return [
            (
                CODE_FINAL,
                1,
                "profile %s draft is %d chars, needs at least %d"
                % (profile, total, spec["min_chars"]),
            )
        ]
    errors = []
    for label, rx in spec["markers"]:
        if not rx.search(text):
            errors.append(
                (CODE_FINAL, 1, "profile %s missing %s marker" % (profile, label))
            )
    return errors


def _coverage_denominator_errors(text):
    lines = text.splitlines()
    marker = None
    for idx, line in enumerate(lines):
        if "coverage_by_source:" in line:
            marker = idx
            break
    if marker is None:
        return [(CODE_COVERAGE, 1, "coverage profile missing coverage_by_source: block")]
    rows = []
    after = lines[marker].split("coverage_by_source:", 1)[1]
    if after.strip():
        rows.append((marker + 1, after.strip()))
    stop = marker + 1
    for idx in range(marker + 1, len(lines)):
        line = lines[idx]
        if not line.strip() or HEADING_RE.match(line) or FENCE_RE.match(line):
            stop = idx
            break
        rows.append((idx + 1, line.strip()))
    else:
        stop = len(lines)
    if not rows:
        return [(CODE_COVERAGE, marker + 1, "coverage_by_source: block has no rows")]
    errors = []
    for lnum, row in rows:
        m = COVERAGE_ROW_RE.match(row)
        if m:
            total = int(m.group(2))
            summed = (
                int(m.group(3))
                + int(m.group(4))
                + int(m.group(5))
                + int(m.group(6))
                + int(m.group(7))
            )
            if summed != total:
                errors.append(
                    (CODE_COVERAGE, lnum,
                     "coverage_by_source row source=%s categories sum to %d but total=%d"
                     % (m.group(1), summed, total))
                )
            continue
        u = UNSCORABLE_ROW_RE.match(row)
        if u:
            continue
        if UNSCORABLE_PREFIX_RE.match(row):
            name = row.split("score=unscorable", 1)[0].split("=", 1)[1].strip()
            errors.append(
                (CODE_COVERAGE, lnum,
                 "coverage_by_source row source=%s is unscorable but has no reason" % name)
            )
            continue
        errors.append((CODE_COVERAGE, lnum, "malformed coverage_by_source row %r" % row))
    tail = [i for i in range(stop, len(lines)) if lines[i].strip()]
    if tail:
        first = tail[0]
        errors.append(
            (CODE_COVERAGE, first + 1,
             "coverage_by_source block must end the final output; %d nonblank "
             "line(s) follow the rows: %r" % (len(tail), lines[first].strip()[:60]))
        )
    return errors


def _paragraph_lines(lines, skip):
    para = []
    for idx, raw in enumerate(lines):
        if FENCE_RE.match(raw) or idx in skip or not raw.strip() or HEADING_RE.match(raw):
            if para:
                yield para
                para = []
            continue
        para.append((idx, raw.strip()))
    if para:
        yield para


def _coverage_source_row_errors(text):
    lines = text.splitlines()
    marker = next((i for i, line in enumerate(lines) if "coverage_by_source:" in line), None)
    if marker is None:
        return []
    block = {marker}
    rows = []
    after = lines[marker].split("coverage_by_source:", 1)[1]
    if after.strip():
        rows.append(after.strip())
    for i in range(marker + 1, len(lines)):
        line = lines[i]
        if not line.strip() or HEADING_RE.match(line) or FENCE_RE.match(line):
            break
        block.add(i)
        rows.append(line.strip())
    sources = set()
    for row in rows:
        m = COVERAGE_ROW_RE.match(row) or UNSCORABLE_ROW_RE.match(row)
        if m:
            val = m.group(1)
        else:
            m2 = re.match(r"^\s*(?:-\s+)?source=([^\s=]+)", row)
            val = m2.group(1) if m2 else None
        if val:
            sources.add(val)
            sources.add(val.rsplit("/", 1)[-1])
    errors = []
    for para in _paragraph_lines(lines, block):
        for lnum, ltext in para:
            for m in MD_LITERAL_RE.finditer(ltext):
                if not _is_omitted_source(ltext, m):
                    continue
                path = m.group(0)
                if path in sources or path.rsplit("/", 1)[-1] in sources:
                    continue
                errors.append(
                    (CODE_COVERAGE, lnum + 1,
                     "coverage paragraph names literal source %r as omitted/"
                     "unextracted/unscorable but coverage_by_source has no matching "
                     "source= row by path or basename" % path)
                )
    return errors


def _length_contract_error(profile, max_chars, no_max_chars):
    """Return (CODE, message) when a structured profile does not get exactly one
    length-contract option, else None. basic and --self-test are exempt."""
    if profile not in CONTRACT_PROFILES:
        return None
    given = int(max_chars is not None) + int(bool(no_max_chars))
    if given == 1:
        return None
    if given == 0:
        return (
            CODE_MAX_CHARS_REQUIRED,
            "profile %s requires exactly one of --max-chars N or --no-max-chars"
            % profile,
        )
    return (
        CODE_MAX_CHARS_REQUIRED,
        "profile %s requires exactly one of --max-chars N or --no-max-chars; "
        "got both --max-chars and --no-max-chars" % profile,
    )


def _margin_contract_error(profile, max_chars, min_margin_pct):
    """Explicitly passing --min-margin-pct without --max-chars on a structured
    profile is a hard failure: a margin requires a ceiling to be measured
    against."""
    if profile not in CONTRACT_PROFILES:
        return None
    if min_margin_pct is not None and max_chars is None:
        return (
            CODE_MARGIN_REQUIRED,
            "profile %s --min-margin-pct requires --max-chars N to define the "
            "ceiling" % profile,
        )
    return None


def _doc_length(text):
    """Mirror the MAX_CHARS counting so margin and ceiling agree: line length
    plus one newline char per line."""
    return sum(len(line) + 1 for line in text.splitlines())


def _margin_errors(profile, text, max_chars, min_margin_pct):
    """A positive margin keeps the draft at or below (100-P)% of the cap.

    Applies whenever --max-chars is given on a structured profile, in both
    emit and non-emit modes, so iteration surfaces MARGIN_EXCEEDED early and
    the single clean --emit run is already inside the margin.
    """
    if profile not in CONTRACT_PROFILES or max_chars is None or not min_margin_pct:
        return []
    total = _doc_length(text)
    limit = max_chars * (100 - min_margin_pct) / 100.0
    if total <= limit:
        return []
    return [
        (
            CODE_MARGIN,
            1,
            "draft is %d chars, exceeds %d%% of --max-chars %d (%d chars); keep "
            "at least %d%% headroom below the cap"
            % (total - 1, 100 - min_margin_pct, max_chars, int(limit), min_margin_pct),
        )
    ]


def _final_wrapper_errors(profile, text):
    """audit/discovery/coverage final answers must begin with a Markdown heading;
    leading narration (e.g. a 'Lint passed'/'Final answer' prefix) fails."""
    if profile not in CONTRACT_PROFILES:
        return []
    for idx, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        if HEADING_RE.match(line):
            return []
        return [
            (CODE_WRAPPER, idx,
             "final answer must begin with a Markdown heading; found leading "
             "narration %r" % line.strip()[:48])
        ]
    return [(CODE_WRAPPER, 1, "final answer is empty")]


def _delim_masked(text):
    out = []
    in_fence = False
    for raw in text.split("\n"):
        if FENCE_RE.match(raw):
            in_fence = not in_fence
            out.append("")
            continue
        if in_fence:
            out.append("")
            continue
        masked = _mask_with(raw, DELIM_URL_RE, " ")
        masked = _mask_with(masked, INLINE_CODE_RE, " ")
        masked = _mask(masked, REF_DEF_RE)
        masked = _mask(masked, HTML_COMMENT_RE)
        masked = _mask(masked, EMOTICON_RE)
        masked = _mask(masked, LIST_ITEM_CLOSE_RE)
        out.append(masked)
    return "\n".join(out)


def _delimiter_errors(text):
    """ASCII/Chinese parentheses and brackets must be balanced after masking code
    fences, inline code, URLs, reference-link definitions, emoticons, and list
    markers, so that normal prose avoids obvious false positives."""
    masked_lines = _delim_masked(text).split("\n")
    errors = []
    for label, op, cl in DELIM_PAIRS:
        opens = sum(line.count(op) for line in masked_lines)
        closes = sum(line.count(cl) for line in masked_lines)
        if opens == closes:
            continue
        lnum = 1
        for i, line in enumerate(masked_lines, start=1):
            if op in line or cl in line:
                lnum = i
                break
        errors.append(
            (CODE_DELIM, lnum,
             "%s unbalanced: %d opening, %d closing" % (label, opens, closes))
        )
    return errors


def _siftline_operation_errors(profile, text):
    """Structured drafts that report a Siftline run must carry the exact names
    machine_attempts, unledgered_attempts, effective_attempts, provider_calls,
    and budget, each with a numeric value; abbreviations are invalid."""
    if profile not in CONTRACT_PROFILES:
        return []
    if not SIFT_TRIGGER_RE.search(text):
        return []
    lnum = 1
    for i, line in enumerate(text.splitlines(), start=1):
        if SIFT_TRIGGER_RE.search(line):
            lnum = i
            break
    errors = []
    for name, rx in SIFT_FIELDS:
        if not rx.search(text):
            errors.append(
                (CODE_SIFT, lnum,
                 "Siftline operation draft missing exact field %s= with a "
                 "numeric value" % name)
            )
    return errors


def lint(text, max_chars=None, profile="basic", min_margin_pct=8):
    """Return a list of (code, line_number, message) violations."""
    errors = []
    draft = text
    lines = text.splitlines()

    in_fence_pre = False
    cap_active = False
    for raw in lines:
        if FENCE_RE.match(raw):
            in_fence_pre = not in_fence_pre
            continue
        if not in_fence_pre and GLOBAL_CAP_RE.search(raw):
            cap_active = True
            break

    if max_chars is not None:
        total = 0
        max_line = None
        for idx, line in enumerate(lines, start=1):
            total += len(line) + 1
            if max_line is None and total > max_chars:
                max_line = idx
        if max_line is not None:
            errors.append(
                (CODE_MAX_CHARS, max_line,
                 "draft is %d chars, exceeds --max-chars %d" % (total - 1, max_chars))
            )

    in_fence = False
    section_level = None
    section_active = False
    para = []

    def flush_para():
        nonlocal para
        if not para:
            return
        joined = "\n".join(p[1] for p in para)
        if LEVEL5_RE.search(joined):
            for lnum, ltext in para:
                m = MARKET_RE.search(ltext)
                if m and not _negated_before(ltext, m.start()):
                    errors.append(
                        (CODE_LEVEL5, lnum,
                         "level-5 paragraph uses demand/market-size language %r" % m.group(0))
                    )
        if (OBSERVED_RE.search(joined)
                and PLAYABLE_RE.search(joined)
                and TEST_CITED_RE.search(joined)
                and not SURFACE_EXERCISED_RE.search(joined)):
            for lnum, ltext in para:
                m = PLAYABLE_RE.search(ltext)
                if m:
                    errors.append(
                        (CODE_STATE_SURFACE, lnum,
                         "observed %r surface claim cites only build/typecheck/unit "
                         "tests without surface-exercised evidence" % m.group(0))
                    )
        if (CODE_VERIFIED_RE.search(joined)
                and SURFACE_CLAIM_RE.search(joined)
                and BUILD_TYPECHECK_RE.search(joined)
                and not FOCUSED_SURFACE_RE.search(joined)
                and not SURFACE_EXERCISED_RE.search(joined)):
            for lnum, ltext in para:
                vm = CODE_VERIFIED_RE.search(ltext)
                if not vm or _negated_before(ltext, vm.start()):
                    continue
                cm = SURFACE_CLAIM_RE.search(ltext)
                if cm and BUILD_TYPECHECK_RE.search(ltext):
                    errors.append(
                        (CODE_STATE_SURFACE, lnum,
                         "code-verified %r claim cites only build/typecheck, "
                         "which never proves playability, availability, or UX"
                         % cm.group(0))
                    )
        if GAP_RE.search(joined):
            bounded = (
                GAP_CHANNEL_RE.search(joined)
                and GAP_QUERY_RE.search(joined)
                and GAP_DATE_RE.search(joined)
            )
            if not bounded:
                for lnum, ltext in para:
                    m = GAP_RE.search(ltext)
                    if m and not _negated_before(ltext, m.start()):
                        errors.append(
                            (CODE_GAP, lnum,
                             "unbounded ecosystem-wide absence phrase %r without "
                             "bounded channels, query/vocabulary, and retrieval "
                             "date in the same paragraph" % m.group(0))
                        )
        norm_joined = _strip_md_emphasis(joined)
        if cap_active or SUCCESS_NEIGHBOR_RE.search(norm_joined):
            for lnum, ltext in para:
                norm = _strip_md_emphasis(ltext)
                if cap_active:
                    for m in MARKET_OVERREACH_RE.finditer(norm):
                        if _negated_before(norm, m.start()):
                            continue
                        errors.append(
                            (CODE_OVERREACH, lnum,
                             "attention-cap draft overclaims %r; only negated "
                             "wording is allowed" % m.group(0))
                        )
                for m in SUCCESS_NEIGHBOR_RE.finditer(norm):
                    if _negated_before(norm, m.start()):
                        continue
                    if cap_active:
                        errors.append(
                            (CODE_OVERREACH, lnum,
                             "attention-cap draft overclaims %r; only negated "
                             "wording is allowed" % m.group(0))
                        )
                        continue
                    if _has_positive_adoption(norm_joined):
                        continue
                    errors.append(
                        (CODE_OVERREACH, lnum,
                         "successful-neighbor wording %r lacks positive non-negated "
                         "direct adoption/outcome evidence" % m.group(0))
                    )
        para = []

    for idx, raw in enumerate(lines, start=1):
        if FENCE_RE.match(raw):
            in_fence = not in_fence
            flush_para()
            continue
        if in_fence:
            continue
        if not raw.strip():
            flush_para()
            continue

        heading = HEADING_RE.match(raw)
        if heading:
            flush_para()
            level = len(heading.group(1))
            if section_active and level <= section_level:
                section_active = False
            if SECTION_RE.search(heading.group(2)):
                section_active = True
                section_level = level
            continue

        text = raw.strip()

        cleaned = _line_clean(text)
        bare = DOMAIN_RE.search(cleaned)
        if bare and not _is_local_filename(cleaned, bare):
            errors.append(
                (CODE_CITATION, idx,
                 "bare citation domain %r without https://" % bare.group(1))
            )

        httpm = HTTP_URL_RE.search(text)
        if httpm:
            errors.append(
                (CODE_HTTPS, idx,
                 "http:// URL %r must use https://" % httpm.group(0))
            )

        causal = CAUSAL_RE.search(text)
        if causal:
            state_here = bool(EVIDENCE_RE.search(text))
            state_next = False
            if not state_here:
                if idx < len(lines):
                    nxt = lines[idx]
                    if nxt.strip():
                        state_next = bool(EVIDENCE_RE.search(nxt))
            if not (state_here or state_next):
                errors.append(
                    (CODE_CAUSAL, idx,
                     "causal phrase %r has no observed/documented/inferred/unverified state" % causal.group(0))
                )

        verified = CODE_VERIFIED_RE.search(text)
        if (
            verified
            and not _negated_before(text, verified.start())
            and not EVIDENCE_LEGEND_RE.match(text)
        ):
            surface_here = bool(SURFACE_MARKER_RE.search(text))
            surface_next = False
            if not surface_here and idx < len(lines):
                nxt = lines[idx]
                if nxt.strip():
                    surface_next = bool(SURFACE_MARKER_RE.search(nxt))
            if not (surface_here or surface_next):
                errors.append(
                    (CODE_VERIFIED, idx,
                     "code-verified claim %r names no exercised surface (a focused "
                     "command, a test run, or a concrete source file)" % verified.group(0))
                )

        if section_active:
            tagged = _line_with_tags(text)
            for m in NUMERAL_RE.finditer(tagged):
                if _is_list_marker(tagged, m):
                    continue
                if _is_range_start(tagged, m.end()):
                    continue
                if not _tag_follows(tagged, m.end()):
                    errors.append(
                        (CODE_THRESHOLD, idx,
                         "numeric criterion %r in test/reversal section lacks an "
                         "immediately following [quoted threshold \u2014 ...] or "
                         "[proposed test threshold]" % m.group(0))
                    )
            for m in CN_NUM_RE.finditer(tagged):
                if not _tag_follows(tagged, m.end()):
                    errors.append(
                        (CODE_THRESHOLD, idx,
                         "Chinese number-word criterion %r in test/reversal section "
                         "lacks an immediately following [quoted threshold \u2014 ...] "
                         "or [proposed test threshold]" % m.group(0))
                    )

        para.append((idx, text))

    flush_para()
    errors.extend(_final_structure_errors(profile, draft))
    errors.extend(_final_wrapper_errors(profile, draft))
    errors.extend(_siftline_operation_errors(profile, draft))
    errors.extend(_delimiter_errors(draft))
    errors.extend(_margin_errors(profile, draft, max_chars, min_margin_pct))
    if profile == "coverage":
        errors.extend(_coverage_denominator_errors(draft))
        errors.extend(_coverage_source_row_errors(draft))
    return errors


def run_lint(text, max_chars, profile="basic", emit=False, min_margin_pct=8):
    errors = lint(text, max_chars, profile, min_margin_pct)
    for code, lnum, msg in errors:
        sys.stdout.write("%s line %d: %s\n" % (code, lnum, msg))
    if not errors:
        if emit:
            sys.stdout.write(text)
        else:
            sys.stdout.write("PASS threshold_unlabeled=0\n")
        return 0
    return 1


_COVERAGE_HEAD = (
    "## Conclusion / \u7ed3\u8bba\n"
    "The core loop is fun and the modding angle drives retention.\n"
    "## Findings / \u53d1\u73b0\n"
    "Observed: play-session logs show users returning to the mod menu. "
    "Documented: the postmortem attributes growth to user-generated content. "
    "Inferred: early-access reviews correlate with mod counts. Unverified: "
    "whether casual players stay after the first week.\n"
    "## Boundary / counterevidence / uncertainty / \u8fb9\u754c\n"
    "The sample is small and short. No counterexample yet: we have not seen a "
    "mod-free cohort retain as well. Uncertainty remains about long-term "
    "retention and about players who never open the workshop.\n"
    "## Next check / \u4e0b\u4e00\u6b65\n"
    "Next check compares retention with and without mod access. Minimum "
    "observation window is four weeks, then compare the two cohorts and record "
    "any reversal.\n"
    "## Coverage source / checklist / \u8986\u76d6\n"
    "Coverage checklist: search GitHub, Steam, App Store and YouTube for each "
    "relation path; log which sources were covered and which were not; note the "
    "retrieval date for every platform.\n"
    "## Matrix / \u77e9\u9635\n"
    "Coverage matrix rows are per platform; each row lists the sources checked, "
    "the markers found, and the gaps still open. Row-level parsing is deferred; "
    "the matrix header and markers are present now.\n"
)


def _coverage_draft(block):
    return _COVERAGE_HEAD + "coverage_by_source:\n" + block + "\n"


def _coverage_draft_note(note, block):
    return _COVERAGE_HEAD + "\n" + note + "\ncoverage_by_source:\n" + block + "\n"


_DISCOVERY_CN = (
    "## 结论\n"
    "核心循环本身是好玩的，而模组入口显著推动留存：拥有模组编辑器的用户回访率更高，"
    "这一关系由官方复盘与游玩会话日志共同支持，但仍需更多证据确认方向。\n"
    "## 需求证据矩阵\n"
    "观察到：游玩会话日志显示用户反复回到模组菜单，回访集中在编辑与分享动作上，"
    "且每次会话都会打开至少一个模组页面。\n"
    "已文档化：官方复盘报告明确将增长归因于用户生成内容，并附有按周划分的留存分段数据表，"
    "其中模组用户的分段留存率始终高于整体。\n"
    "推断：早期评测与模组数量正相关，评测者更频繁地提到可编辑性与创作自由，"
    "说明工坊目录是吸引注意力的有效入口。\n"
    "未验证：休闲玩家是否在首周之后继续留下，从不打开工坊的玩家留存如何，"
    "以及不同模组类型之间的差异，当前均无对应数据。\n"
    "## 证据边界\n"
    "当前样本量小且观察窗口短，无法排除选择偏差，因此结论只能作为阶段性判断，"
    "不能推广到全部玩家群体。\n"
    "反证：尚未观察到无模组对照组同样能留存的证据，也未见到工坊缺位时留存反而上升的反例；"
    "这两类情况一旦出现，就会削弱当前结论。\n"
    "不确定性：长期留存趋势、玩家来源分布、平台推荐算法的实际影响以及内容监管政策的变化"
    "均未知，这些限制意味着我们应当谨慎对待因果方向，优先补足缺失数据。\n"
    "## 下一步\n"
    "下一步对比开启与关闭模组访问的两组留存率，同时记录两组玩家的游玩时长、回访频次和"
    "工坊浏览深度，确保两组在进入条件上可比。\n"
    "最小观察窗口为四周，之后比较两组数据并记录任何反转；若四周内模组组留存率未显著高于"
    "对照组，则标记为待验证并调整当前判断，必要时补充新假设。"
)


SIFT_EVIDENCE = (
    "Evidence state: observed from the machine ledger and the serial transcript, "
    "documented in the run notes, inferred for the unledgered parser failure, and "
    "unverified for any provider outcome that the ledger did not record. "
    "Source: siftline ledger --query-id run-2026-08-10-a --limit 100, retrieved "
    "2026-08-10. All external operations used the one stable query ID and ran "
    "strictly serial before the freeze at attempt 6 of 8."
)


AUDIT_DRAFT_VALID = (
    "## Conclusion / \u7ed3\u8bba\n"
    "The modding loop is the core driver of retention (documented in the official "
    "postmortem; observed in play-session data; inferred from Steam reviews; "
    "unverified alternatives noted).\n"
    "## Evidence state / \u8bc1\u636e\u72b6\u6001\n"
    "observed, documented, inferred and unverified markers are each declared with "
    "a timestamp and a retrieval date.\n"
    "## Source / Command / \u6765\u6e90\n"
    "Source: https://github.com/acme/project. Command: python scripts/audit.py "
    "--run. Retrieved 2026-08-10."
)


SELF_TESTS = [
    ("max-chars fail", 100 * "x", {"max_chars": 50}, [CODE_MAX_CHARS]),
    ("max-chars pass", "hello", {"max_chars": 50}, []),
    (
        "citation fail",
        "Source: github.com/acme/project says it runs everywhere.",
        {}, [CODE_CITATION],
    ),
    (
        "citation pass",
        "Source: https://github.com/acme/project says it runs everywhere.",
        {}, [],
    ),
    (
        "citation pass masked url",
        "The link is https://x.github.io/docs and nothing else.",
        {}, [],
    ),
    (
        "causal fail",
        "Its success is due to low price.",
        {}, [CODE_CAUSAL],
    ),
    (
        "causal pass",
        "Its success is due to low price (inferred; no source).",
        {}, [],
    ),
    (
        "level5 fail",
        "~4k stars is still a strong demand signal for the market.",
        {}, [CODE_LEVEL5],
    ),
    (
        "level5 pass negated",
        "~4k stars (Steam, 2026-08-10) is attention/discovery only; it does not prove demand.",
        {}, [],
    ),
    (
        "threshold fail bare",
        "## Test Criteria\nA candidate must have 5+ contributors to pass.",
        {}, [CODE_THRESHOLD],
    ),
    (
        "threshold pass quoted",
        "## Test Criteria\nAccept only when >=60%[quoted threshold \u2014 docs/22 \u00a710] "
        "with 8 \u540d[quoted threshold \u2014 docs/18 \u00a711].",
        {}, [],
    ),
    (
        "threshold fail sentence-end",
        "## Reversal Conditions\n10 participants, 60%, >=1 retry [proposed test threshold] "
        "trigger a reversal.",
        {}, [CODE_THRESHOLD, CODE_THRESHOLD],
    ),
    (
        "threshold pass reversal",
        "## Reversal Conditions\nReversal triggers when score drops >=10 \u70b9[proposed test threshold].",
        {}, [],
    ),
    (
        "threshold fail mechanic",
        "## Reversal Conditions\nHeat >= 10 triggers overtime; a 2-second protection window follows.",
        {}, [CODE_THRESHOLD, CODE_THRESHOLD],
    ),
    (
        "max-chars omitted no limit",
        1000 * "x", {}, [],
    ),
    (
        "state surface fail",
        "The game is playable and fun; playable observed because the build passed and the typecheck passed.",
        {}, [CODE_STATE_SURFACE],
    ),
    (
        "state surface pass exercised",
        "The game is playable (observed); I launched it, ran the game in a browser session, "
        "and played through the loop.",
        {}, [],
    ),
    (
        "state surface pass build-no-observed",
        "The build passed; the game is playable and fun.",
        {}, [],
    ),
    (
        "causal generic because pass",
        "The build passed because the unit test was fixed, therefore the loop is playable.",
        {}, [],
    ),
    (
        "causal success came from fail",
        "Its success came from being open source.",
        {}, [CODE_CAUSAL],
    ),
    (
        "minimum observation heading fail",
        "## minimum observation\nA drop below 3 \u5929 flips the call.",
        {}, [CODE_THRESHOLD],
    ),
    (
        "\u63a8\u7ffb heading fail",
        "## \u63a8\u7ffb\n\u4e00\u65e6\u8dcc\u7834 3 \u4e2a\u767e\u5206\u70b9\u5373\u53cd\u8f6c\u3002",
        {}, [CODE_THRESHOLD],
    ),
    (
        "ordered list markers ignored",
        "## Reversal Conditions\n1. Drop >=10 \u70b9[proposed test threshold]\n"
        "2. Keep 5 \u540d[quoted threshold \u2014 docs/18 \u00a711]",
        {}, [],
    ),
    (
        "url and source refs ignored",
        "## Reversal Conditions\nSee https://github.com/acme/issues/5 and docs/18 \u00a711 "
        "before setting 4 \u540d[proposed test threshold].",
        {}, [],
    ),
    (
        "chinese number word fail",
        "## Reversal Conditions\n\u6ee1\u8db3\u4e09\u540d\u7684\u7559\u5b58\u5373\u53ef\u89e6\u53d1\u3002",
        {}, [CODE_THRESHOLD],
    ),
    (
        "chinese number word pass",
        "## Reversal Conditions\n\u6ee1\u8db3\u4e09\u540d[proposed test threshold]\u5373\u53ef\u3002",
        {}, [],
    ),
    (
        "level5 attention fail",
        "This project received a lot of attention; that proves strong demand.",
        {}, [CODE_LEVEL5],
    ),
    (
        "level5 attention pass only",
        "Attention is a discovery signal; it does not prove demand.",
        {}, [],
    ),
    (
        "level5 review fail",
        "~100 reviews on Steam prove \u5f3a\u9700\u6c42.",
        {}, [CODE_LEVEL5],
    ),
    (
        "level5 cn review fail",
        "\u8bc4\u8bba\u533a\u7684\u5c0f\u4f17\u4fe1\u53f7\u88ab\u5f53\u6210\u9700\u6c42\u3002",
        {}, [CODE_LEVEL5],
    ),
    (
        "level5 audience fail",
        "Review totals are high; \u53d7\u4f17\u5de8\u5927 follows.",
        {}, [CODE_LEVEL5],
    ),
    (
        "level5 \u8bc4\u6d4b fail",
        "\u8bc4\u6d4b\u663e\u793a\u5f3a\u9700\u6c42\u3002",
        {}, [CODE_LEVEL5],
    ),
    (
        "local md filename pass",
        "The README.md describes the loop; SKILL.md too.",
        {}, [],
    ),
    (
        "local toml filename pass",
        "See pyproject.toml and config.example.yaml for details.",
        {}, [],
    ),
    (
        "local json py pass",
        "index.py, data.json and notes.txt are local files.",
        {}, [],
    ),
    (
        "md domain with path fail",
        "Site: foo.md/contact for more info.",
        {}, [CODE_CITATION],
    ),
    (
        "clean document",
        "## Test Criteria\n5 \u540d[quoted threshold \u2014 docs/18 \u00a711] must stay engaged.\n\n"
        "## Findings\nThe game succeeded due to modding (observed \u2014 official postmortem, "
        "retrieved 2026-08-10).\nSource: https://github.com/acme/project. "
        "~2k stars is attention only; it proves nothing.",
        {}, [],
    ),
    (
        "clean with cn headings",
        "## \u6700\u5c0f\u89c2\u5bdf\n\u81f3\u5c11 5 \u540d[quoted threshold \u2014 docs/20 \u00a73] "
        "\u7559\u5b58\uff0c\u6216\u8dcc\u7834 3 \u5929[proposed test threshold] \u89e6\u53d1\u63a8\u7ffb\u3002\n\n"
        "## \u63a8\u7ffb\nscore \u8dcc\u7834 10 \u70b9[proposed test threshold]\u3002",
        {}, [],
    ),
    (
        "short progress message fails discovery",
        "Progress update: shipped an alpha build to a small test group.",
        {"profile": "discovery"},
        [CODE_FINAL, CODE_WRAPPER],
    ),
    (
        "audit profile valid compact",
        AUDIT_DRAFT_VALID,
        {"profile": "audit"},
        [],
    ),
    (
        "discovery profile valid compact",
        "## Conclusion / \u7ed3\u8bba\n"
        "The core loop is fun and the modding angle drives retention.\n"
        "## Findings / \u53d1\u73b0\n"
        "Observed: play-session logs show users returning to the mod menu. "
        "Documented: the postmortem attributes growth to user-generated content. "
        "Inferred: early-access reviews correlate with mod counts. Unverified: "
        "whether casual players stay after the first week.\n"
        "## Boundary / counterevidence / uncertainty / \u8fb9\u754c\n"
        "The sample is small and short. No counterexample yet: we have not seen a "
        "mod-free cohort retain as well. Uncertainty remains about long-term "
        "retention and about players who never open the workshop.\n"
        "## Next check / \u4e0b\u4e00\u6b65\n"
        "Next check compares retention with and without mod access. Minimum "
        "observation window is four weeks, then compare the two cohorts and record "
        "any reversal.",
        {"profile": "discovery"},
        [],
    ),
    (
        "discovery profile valid cn headings",
        _DISCOVERY_CN,
        {"profile": "discovery"},
        [],
    ),
    (
        "coverage profile valid cn headings",
        _DISCOVERY_CN
        + "\n## 覆盖\n"
        "覆盖清单：对每个关系路径检索 GitHub、Steam、应用商店与视频平台，记录哪些来源已覆盖、"
        "哪些未覆盖，并为每个平台标注检索日期。\n"
        "coverage_by_source:\n"
        "source=github total=3 implemented=2 partial=1 planned=0 absent=0 unmapped=0\n"
        "source=steam score=unscorable reason=no api access",
        {"profile": "coverage"},
        [],
    ),
    (
        "coverage profile valid compact",
        _coverage_draft(
            "source=github total=3 implemented=2 partial=1 planned=0 absent=0 unmapped=0\n"
            "source=steam score=unscorable reason=no api access"
        ),
        {"profile": "coverage"},
        [],
    ),
    (
        "coverage missing block fail",
        _COVERAGE_HEAD,
        {"profile": "coverage"},
        [CODE_COVERAGE],
    ),
    (
        "coverage no rows fail",
        _coverage_draft(""),
        {"profile": "coverage"},
        [CODE_COVERAGE],
    ),
    (
        "coverage malformed row fail",
        _coverage_draft("source=github total=3 implemented=2 partial=1"),
        {"profile": "coverage"},
        [CODE_COVERAGE],
    ),
    (
        "coverage mismatch fail",
        _coverage_draft(
            "source=github total=5 implemented=2 partial=1 planned=0 absent=0 unmapped=1"
        ),
        {"profile": "coverage"},
        [CODE_COVERAGE],
    ),
    (
        "coverage unscorable no reason fail",
        _coverage_draft("source=steam score=unscorable"),
        {"profile": "coverage"},
        [CODE_COVERAGE],
    ),
    (
        "coverage unscorable empty reason fail",
        _coverage_draft("source=steam score=unscorable reason="),
        {"profile": "coverage"},
        [CODE_COVERAGE],
    ),
    (
        "coverage valid rows pass",
        _coverage_draft(
            "source=github total=3 implemented=2 partial=1 planned=0 absent=0 unmapped=0\n"
            "source=steam score=unscorable reason=no api access\n"
            "source=hn total=0 implemented=0 partial=0 planned=0 absent=0 unmapped=0"
        ),
        {"profile": "coverage"},
        [],
    ),
    (
        "coverage bullet rows pass",
        _coverage_draft(
            "- source=github total=3 implemented=2 partial=1 planned=0 absent=0 unmapped=0\n"
            "- source=steam score=unscorable reason=no api access\n"
            "- source=hn total=0 implemented=0 partial=0 planned=0 absent=0 unmapped=0"
        ),
        {"profile": "coverage"},
        [],
    ),
    (
        "coverage bullet mismatch fail",
        _coverage_draft(
            "- source=github total=5 implemented=2 partial=1 planned=0 absent=0 unmapped=1"
        ),
        {"profile": "coverage"},
        [CODE_COVERAGE],
    ),
    (
        "bounded gap fail poiema",
        "\u63a8\u7ffb\u5168\u94fe\u8def\u751f\u6001\u7f3a\u53e3\u3002",
        {}, [CODE_GAP],
    ),
    (
        "bounded gap fail unbounded english",
        "There is a real gap in this ecosystem; no competitor exists anywhere.",
        {}, [CODE_GAP],
    ),
    (
        "bounded gap fail partial bounds",
        "\u65e0\u4eba\u505a\uff1a\u5728 GitHub \u7528\u5173\u952e\u8bcd\u641c\u7d22\uff0c"
        "\u672a\u53d1\u73b0\u7b49\u4ef7\u7269\u3002",
        {}, [CODE_GAP],
    ),
    (
        "bounded gap pass cn",
        "\u65e0\u4eba\u505a\uff1a\u5728 GitHub \u7528\u5173\u952e\u8bcd\u641c\u7d22\uff0c"
        "\u68c0\u7d22\u4e8e 2026-08-10\uff0c\u672a\u53d1\u73b0\u7b49\u4ef7\u7269\u3002",
        {}, [],
    ),
    (
        "bounded gap pass en",
        "No competitor found on Steam for the query \"pet sim\", "
        "retrieved 2026-08-10.",
        {}, [],
    ),
    (
        "bounded gap pass retrieved_at",
        "No competitor found on Steam for the query \"pet sim\", "
        "retrieved_at=2026-08-10.",
        {}, [],
    ),
    (
        "bounded gap pass retrieval cn space",
        "\u65e0\u4eba\u505a\uff1a\u5728 GitHub \u7528\u5173\u952e\u8bcd\u641c\u7d22\uff0c"
        "\u68c0\u7d22 2026-08-10\uff0c\u672a\u53d1\u73b0\u7b49\u4ef7\u7269\u3002",
        {}, [],
    ),
    (
        "bounded gap negated pass",
        "It is not a real gap; the market is fine.",
        {}, [],
    ),
    (
        "threshold version id masked pass",
        "## Reversal Conditions\nShip P1.6, then P3; gate on v0.1 and V2.0.",
        {}, [],
    ),
    (
        "threshold version id preserve criteria",
        "## Reversal Conditions\nKeep 5 players at P1.6; revert below 3 at V2.0.",
        {}, [CODE_THRESHOLD, CODE_THRESHOLD],
    ),
    (
        "threshold version id only masked pass",
        "## Test Criteria\nGate on v0.1 milestones only.",
        {}, [],
    ),
    (
        "implementation-status cn punctuation pass",
        "IMPLEMENTATION-STATUS.md\u3002\u8be5\u6587\u4ef6\u8bb0\u5f55\u4e86\u5b9e\u73b0"
        "\u72b6\u6001\u3002",
        {}, [],
    ),
    (
        "http url fail",
        "Source: http://github.com/acme/project says it runs everywhere.",
        {}, [CODE_HTTPS],
    ),
    (
        "http url quote stops before punctuation",
        "Source: http://github.com/acme/project，很好。",
        {}, [CODE_HTTPS],
    ),
    (
        "http url pass https",
        "Source: https://github.com/acme/project says it runs everywhere.",
        {}, [],
    ),
    (
        "http url in fence ignored",
        "Some text.\n```\nhttp://example.com/\n```\nMore text.",
        {}, [],
    ),
    (
        "attention cap overreach 机制吸引力中等 fail",
        "All external evidence is attention-only. 机制吸引力中等。",
        {}, [CODE_OVERREACH],
    ),
    (
        "attention cap overreach 获主流采纳 fail",
        "All external evidence is attention-only. 该项目获主流采纳。",
        {}, [CODE_OVERREACH],
    ),
    (
        "attention cap overreach 已是竞争基线 fail",
        "All external evidence is attention-only. 已是竞争基线。",
        {}, [CODE_OVERREACH],
    ),
    (
        "attention cap overreach 痛点 fail",
        "All external evidence is attention-only. 痛点在生态中真实存在。",
        {}, [CODE_OVERREACH],
    ),
    (
        "attention cap overreach 玩家痴迷 fail",
        "All external evidence is attention-only. 玩家痴迷。",
        {}, [CODE_OVERREACH],
    ),
    (
        "attention cap overreach successful neighbor fail",
        "All external evidence is attention-only. It is a successful neighbor.",
        {}, [CODE_OVERREACH],
    ),
    (
        "attention cap cn 获主流采纳 fail",
        "所有外部证据均为5级。获主流采纳。",
        {}, [CODE_OVERREACH],
    ),
    (
        "attention cap caveat 不能证明主流采纳 pass",
        "All external evidence is attention-only. 不能证明主流采纳。",
        {}, [],
    ),
    (
        "attention cap safe candidate pass",
        "All external evidence is attention-only. 在本轮检索到的若干候选中反复作为卖点。",
        {}, [],
    ),
    (
        "attention cap safe single-user pass",
        "All external evidence is attention-only. 单用户陈述显示该用户有此痛点。",
        {}, [],
    ),
    (
        "attention cap candidate does not exempt 机制吸引力中等 fail",
        "All external evidence is attention-only. 在该候选中反复作为卖点，机制吸引力中等。",
        {}, [CODE_OVERREACH],
    ),
    (
        "attention cap candidate-only sentence pass",
        "All external evidence is attention-only. 在本轮检索到的若干候选中仅作为候选被记录。",
        {}, [],
    ),
    (
        "attention cap candidate does not exempt neighbor label fail",
        "All external evidence is attention-only. 该候选是成功近邻候选，未核实采用结果。",
        {}, [CODE_OVERREACH],
    ),
    (
        "attention cap worldloom 机制吸引力中等 fail",
        "需求强度只能封顶为 attention + 显式子机制请求。机制吸引力中等。",
        {}, [CODE_OVERREACH],
    ),
    (
        "attention cap worldloom 为竞争基线 fail",
        "需求强度只能封顶为 attention + 显式子机制请求。为竞争基线。",
        {}, [CODE_OVERREACH],
    ),
    (
        "attention cap worldloom 佐证竞争基线 fail",
        "需求强度只能封顶为 attention + 显式子机制请求。佐证了竞争基线。",
        {}, [CODE_OVERREACH],
    ),
    (
        "attention cap worldloom negated 竞争基线 pass",
        "需求强度只能封顶为 attention + 显式子机制请求。不能证明是竞争基线。",
        {}, [],
    ),
    (
        "attention cap bold 机制吸引力**中等** fail",
        "All external evidence is attention-only. 机制吸引力**中等**。",
        {}, [CODE_OVERREACH],
    ),
    (
        "attention cap bold **获主流采纳** fail",
        "All external evidence is attention-only. **获主流采纳**。",
        {}, [CODE_OVERREACH],
    ),
    (
        "attention cap bold **成功近邻** fail",
        "All external evidence is attention-only. **成功近邻**。",
        {}, [CODE_OVERREACH],
    ),
    (
        "attention cap bold negated 不能证明**主流采纳** pass",
        "All external evidence is attention-only. 不能证明**主流采纳**。",
        {}, [],
    ),
    (
        "attention cap worldloom neighbor intervening fail",
        "需求强度只能封顶为 attention + 显式子机制请求。最近的成功合作法术 ARPG 邻居。",
        {}, [CODE_OVERREACH],
    ),
    (
        "no cap 机制吸引力中等 pass",
        "机制吸引力中等，说明方向存在一定潜力。",
        {}, [],
    ),
    (
        "successful neighbor no evidence fail",
        "It is positioned as a successful neighbor of the leading project.",
        {}, [CODE_OVERREACH],
    ),
    (
        "successful neighbor with adoption evidence pass",
        "The successful neighbor is already adopted by three studios (documented).",
        {}, [],
    ),
    (
        "successful neighbor negated adoption not evidence fail",
        "The successful neighbor was never adopted by anyone.",
        {}, [CODE_OVERREACH],
    ),
    (
        "standalone failure neighbor cn pass",
        "该项目是失败近邻，属正常研究类别。",
        {}, [],
    ),
    (
        "standalone failed neighbor en pass",
        "It is a failed neighbor of the leading project.",
        {}, [],
    ),
    (
        "mixed success/failure neighbor phrase still fails",
        "最近的成功/失败合作法术 ARPG 邻居。",
        {}, [CODE_OVERREACH],
    ),
    (
        "successful neighbor 未被采用 not evidence fail",
        "该成功近邻未被采用。",
        {}, [CODE_OVERREACH],
    ),
    (
        "successful neighbor 尚未被采用 not evidence fail",
        "该成功近邻尚未被采用。",
        {}, [CODE_OVERREACH],
    ),
    (
        "successful neighbor cn no evidence fail",
        "该项目是成功近邻。",
        {}, [CODE_OVERREACH],
    ),
    (
        "successful neighbor cn unverified outcome still fails",
        "成功近邻，未核实采用结果。",
        {}, [CODE_OVERREACH],
    ),
    (
        "successful neighbor caveat 未核实采用结果的近邻候选 pass",
        "未核实采用结果的近邻候选。",
        {}, [],
    ),
    (
        "coverage omitted md row present pass",
        _coverage_draft_note(
            "docs/overview.md 遗漏在检索清单中。",
            "source=docs/overview.md total=2 implemented=1 partial=1 planned=0 absent=0 unmapped=0\n"
            "source=github total=3 implemented=2 partial=1 planned=0 absent=0 unmapped=0",
        ),
        {"profile": "coverage"},
        [],
    ),
    (
        "coverage omitted md basename match pass",
        _coverage_draft_note(
            "README.md 未提取。",
            "source=docs/README.md total=1 implemented=0 partial=0 planned=1 absent=0 unmapped=0",
        ),
        {"profile": "coverage"},
        [],
    ),
    (
        "coverage omitted english md row pass",
        _coverage_draft_note(
            "The file docs/notes.md was omitted and unextracted.",
            "source=docs/notes.md total=2 implemented=2 partial=0 planned=0 absent=0 unmapped=0",
        ),
        {"profile": "coverage"},
        [],
    ),
    (
        "coverage omitted md row missing fail",
        _coverage_draft_note(
            "docs/overview.md 遗漏在检索清单中。",
            "source=github total=3 implemented=2 partial=1 planned=0 absent=0 unmapped=0",
        ),
        {"profile": "coverage"},
        [CODE_COVERAGE],
    ),
    (
        "coverage unextracted md basename missing fail",
        _coverage_draft_note(
            "README.md 未评分。",
            "source=github total=3 implemented=2 partial=1 planned=0 absent=0 unmapped=0",
        ),
        {"profile": "coverage"},
        [CODE_COVERAGE],
    ),
    (
        "coverage 遗漏痛点 unrelated md not associated pass",
        _coverage_draft_note(
            "遗漏痛点 docs/10-v0.1-prd.md 需要保留。",
            "source=github total=3 implemented=2 partial=1 planned=0 absent=0 unmapped=0",
        ),
        {"profile": "coverage"},
        [],
    ),
    (
        "coverage extracted md then omitted only omitted required pass",
        _coverage_draft_note(
            "README.md 已提取，遗漏: docs/x.md。",
            "source=docs/x.md total=1 implemented=1 partial=0 planned=0 absent=0 unmapped=0",
        ),
        {"profile": "coverage"},
        [],
    ),
    (
        "coverage extracted md then omitted missing row fail",
        _coverage_draft_note(
            "README.md 已提取，遗漏: docs/x.md。",
            "source=github total=3 implemented=2 partial=1 planned=0 absent=0 unmapped=0",
        ),
        {"profile": "coverage"},
        [CODE_COVERAGE],
    ),
    (
        "siftline missing effective_attempts fail",
        "## Conclusion\n"
        "The Siftline run for query_id run-2026-08-10-a completed. "
        "machine_attempts=5 unledgered_attempts=1 provider_calls=4 budget=8. "
        + SIFT_EVIDENCE,
        {"profile": "audit"},
        [CODE_SIFT],
    ),
    (
        "siftline all five exact fields pass",
        "## Conclusion\n"
        "The Siftline run for query_id run-2026-08-10-a completed. "
        "machine_attempts=5 unledgered_attempts=1 effective_attempts=6 "
        "provider_calls=4 budget=8. "
        + SIFT_EVIDENCE,
        {"profile": "audit"},
        [],
    ),
    (
        "siftline abbreviated fields fail",
        "## Conclusion\n"
        "Siftline query run done. ma=5 unledgered=1 eff=6 provider=4 b=8. "
        + SIFT_EVIDENCE,
        {"profile": "audit"},
        [CODE_SIFT, CODE_SIFT, CODE_SIFT, CODE_SIFT, CODE_SIFT],
    ),
    (
        "siftline mentions not required in basic",
        "Siftline ran with provider_calls=2 but no fields listed.",
        {},
        [],
    ),
    (
        "unbalanced chinese parens 25/24 fail",
        "\uff08" * 25 + "x" + "\uff09" * 24,
        {},
        [CODE_DELIM],
    ),
    (
        "balanced chinese parens pass",
        "\uff08a\uff09\uff08b\uff09\uff08c\uff09",
        {},
        [],
    ),
    (
        "unbalanced ascii parens fail",
        "foo(bar",
        {},
        [CODE_DELIM],
    ),
    (
        "unbalanced ascii brackets fail",
        "see [issue 5",
        {},
        [CODE_DELIM],
    ),
    (
        "unbalanced chinese brackets fail",
        "\u3010note",
        {},
        [CODE_DELIM],
    ),
    (
        "balanced mixed delimiters pass",
        "a（b）c [d] \u3010e\u3011 (f)",
        {},
        [],
    ),
    (
        "delimiters in code fence ignored",
        "before\n```\n( ) （ ） [ ] 【 】\n```\nafter",
        {},
        [],
    ),
    (
        "delimiters in inline code and url ignored",
        "see `(` and `)` and https://example.com/a(b) and `[x` ok",
        {},
        [],
    ),
    (
        "ordered list close paren masked",
        "1) alpha\n2) beta\nplain text (kept).",
        {},
        [],
    ),
    (
        "reference link definition balanced",
        "See [1]: https://example.com/doc and cite (text).",
        {},
        [],
    ),
    (
        "wrapper prefix narration fails",
        "Lint passed. Final answer:\n" + _DISCOVERY_CN,
        {"profile": "discovery"},
        [CODE_WRAPPER],
    ),
    (
        "coverage prose after rows fail",
        _coverage_draft(
            "source=github total=3 implemented=2 partial=1 planned=0 absent=0 unmapped=0\n"
            "source=steam score=unscorable reason=no api access"
        ) + "Trailing prose must not follow the block.",
        {"profile": "coverage"},
        [CODE_COVERAGE],
    ),
    (
        "coverage heading after rows fail",
        _coverage_draft(
            "source=github total=3 implemented=2 partial=1 planned=0 absent=0 unmapped=0"
        ) + "\n## Not the end\nA section after the block.",
        {"profile": "coverage"},
        [CODE_COVERAGE],
    ),
    (
        "margin fail long draft",
        AUDIT_DRAFT_VALID,
        {"profile": "audit", "max_chars": _doc_length(AUDIT_DRAFT_VALID)},
        [CODE_MARGIN],
    ),
    (
        "margin pass short draft",
        AUDIT_DRAFT_VALID,
        {"profile": "audit", "max_chars": _doc_length(AUDIT_DRAFT_VALID) * 2},
        [],
    ),
    (
        "margin pass long no-max-chars",
        AUDIT_DRAFT_VALID,
        {"profile": "audit", "no_max_chars": True},
        [],
    ),
    (
        "margin custom pct fail",
        AUDIT_DRAFT_VALID,
        {
            "profile": "audit",
            "max_chars": _doc_length(AUDIT_DRAFT_VALID),
            "min_margin_pct": 10,
        },
        [CODE_MARGIN],
    ),
    (
        "margin custom pct pass",
        AUDIT_DRAFT_VALID,
        {
            "profile": "audit",
            "max_chars": _doc_length(AUDIT_DRAFT_VALID) * 2,
            "min_margin_pct": 10,
        },
        [],
    ),
    (
        "code-verified no surface fail",
        "The seed loop is code-verified.",
        {}, [CODE_VERIFIED],
    ),
    (
        "code-verified with focused test pass",
        "The loop is code-verified: I ran npm test -- src/loop.test.ts.",
        {}, [],
    ),
    (
        "code-verified with source file pass",
        "The auth flow is code-verified after reading apps/desktop/src/main/ipc.ts.",
        {}, [],
    ),
    (
        "code-verified cn no surface fail",
        "该机制已代码核验。",
        {}, [CODE_VERIFIED],
    ),
    (
        "code-verified cn focused test pass",
        "该机制已代码核验：实际运行了 pytest tests/test_core.py。",
        {}, [],
    ),
    (
        "code-verified build does not surface playability pass via negation",
        "The build passed but playability stays documented, not code-verified.",
        {}, [],
    ),
    (
        "evidence state legend pass",
        "Evidence states: observed, documented, inferred, unverified, code-verified.",
        {}, [],
    ),
    (
        "evidence state legend bare pass",
        "observed, documented, inferred, unverified, code-verified",
        {}, [],
    ),
    (
        "evidence state legend cn pass",
        "证据状态：已观察、已文档化、推断、未验证、已代码核验。",
        {}, [],
    ),
    (
        "code-verified build-only playability fail",
        "Playability is code-verified after npm run build/typecheck.",
        {}, [CODE_STATE_SURFACE],
    ),
    (
        "code-verified build-only ux fail",
        "UX is 已代码核验：仅运行了 npm run build。",
        {}, [CODE_STATE_SURFACE],
    ),
    (
        "code-verified focused test parser pass",
        "Parser behavior is code-verified by tests/test_parser.py.",
        {}, [],
    ),
    (
        "code-verified focused pytest pass",
        "Parser behavior is code-verified: focused pytest tests/test_parser.py passed.",
        {}, [],
    ),
]


def _capture_run(text, max_chars=None, profile="basic", emit=False, min_margin_pct=8):
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        code = run_lint(text, max_chars, profile, emit, min_margin_pct)
    finally:
        sys.stdout = old
    return code, buf.getvalue()


def _run_emit_echo():
    text = "clean draft line\n"
    code, out = _capture_run(text, emit=True)
    ok = code == 0 and out == text
    return ok, "code=%d out=%r" % (code, out)


def _run_no_emit_pass():
    text = "clean draft line\n"
    code, out = _capture_run(text)
    ok = code == 0 and out == "PASS threshold_unlabeled=0\n"
    return ok, "code=%d out=%r" % (code, out)


def _run_emit_echo_with_max_chars():
    text = "clean\n"
    code, out = _capture_run(text, max_chars=50, emit=True)
    ok = code == 0 and out == text
    return ok, "code=%d out=%r" % (code, out)


def _run_emit_error():
    text = "Its success is due to low price."
    code, out = _capture_run(text, emit=True)
    ok = code == 1 and out.startswith("CAUSAL_UNTAGGED line 1:")
    return ok, "code=%d out=%r" % (code, out)


def _run_http_quote():
    code, out = _capture_run("Source: http://github.com/acme/project，很好。")
    want = "HTTPS_REQUIRED line 1: http:// URL 'http://github.com/acme/project' must use https://\n"
    ok = code == 1 and out == want
    return ok, "code=%d out=%r" % (code, out)


def _capture_main(argv):
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out_buf, err_buf
    try:
        try:
            code = main(argv)
        except SystemExit as exc:
            code = exc.code
            if code is None:
                code = 0
            elif not isinstance(code, int):
                code = 1
    finally:
        sys.stdout, sys.stderr = old_out, old_err
    return code, out_buf.getvalue(), err_buf.getvalue()


def _run_contract_missing_both_cli():
    code, out, err = _capture_main(["--profile", "audit"])
    ok = code == 2 and "MAX_CHARS_REQUIRED" in err and "--no-max-chars" in err
    return ok, "code=%d out=%r err=%r" % (code, out, err)


def _run_contract_given_both_cli():
    code, out, err = _capture_main(
        ["--profile", "coverage", "--max-chars", "1000", "--no-max-chars"]
    )
    ok = code == 2 and "MAX_CHARS_REQUIRED" in err and "both" in err
    return ok, "code=%d out=%r err=%r" % (code, out, err)


def _run_contract_pass_max_chars_cli():
    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(AUDIT_DRAFT_VALID)
        path = fh.name
    try:
        code, out, err = _capture_main(
            ["--profile", "audit", "--max-chars", "5000", "--file", path]
        )
        ok = code == 0 and err == ""
    finally:
        os.unlink(path)
    return ok, "code=%d out=%r err=%r" % (code, out, err)


def _run_contract_pass_no_max_chars_cli():
    with tempfile.NamedTemporaryFile(
        "w", suffix=".md", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(AUDIT_DRAFT_VALID)
        path = fh.name
    try:
        code, out, err = _capture_main(
            ["--profile", "audit", "--no-max-chars", "--file", path]
        )
        ok = code == 0 and err == ""
    finally:
        os.unlink(path)
    return ok, "code=%d out=%r err=%r" % (code, out, err)


def _run_contract_helper():
    checks = [
        ("basic exempt neither", _length_contract_error("basic", None, False) is None),
        ("audit max-chars ok", _length_contract_error("audit", 500, False) is None),
        ("audit no-max ok", _length_contract_error("audit", None, True) is None),
        ("discovery max-chars ok", _length_contract_error("discovery", 700, False) is None),
        ("discovery no-max ok", _length_contract_error("discovery", None, True) is None),
        ("coverage max-chars ok", _length_contract_error("coverage", 900, False) is None),
        ("coverage no-max ok", _length_contract_error("coverage", None, True) is None),
        ("audit neither flagged", _length_contract_error("audit", None, False) is not None),
        ("discovery neither flagged", _length_contract_error("discovery", None, False) is not None),
        ("coverage neither flagged", _length_contract_error("coverage", None, False) is not None),
        ("audit both flagged", _length_contract_error("audit", 500, True) is not None),
        ("discovery both flagged", _length_contract_error("discovery", 700, True) is not None),
        ("coverage both flagged", _length_contract_error("coverage", 900, True) is not None),
        (
            "error code is MAX_CHARS_REQUIRED",
            _length_contract_error("audit", None, False)[0] == CODE_MAX_CHARS_REQUIRED,
        ),
        ("margin requires max-chars", _margin_contract_error("audit", None, 8) is not None),
        ("margin ok with max-chars", _margin_contract_error("audit", 500, 8) is None),
        ("margin ok no-max", _margin_contract_error("audit", None, None) is None),
        ("basic margin exempt", _margin_contract_error("basic", None, 8) is None),
    ]
    bad = [name for name, ok in checks if not ok]
    return not bad, "failed checks: %s" % (bad,)


def _run_margin_requires_max_chars_cli():
    code, out, err = _capture_main(
        ["--profile", "audit", "--min-margin-pct", "8", "--no-max-chars"]
    )
    ok = code == 2 and "MARGIN_REQUIRES_MAX_CHARS" in err and "--max-chars" in err
    return ok, "code=%d out=%r err=%r" % (code, out, err)


def _run_margin_emit_fail():
    text = AUDIT_DRAFT_VALID
    total = _doc_length(text)
    max_chars = total
    code, out = _capture_run(text, max_chars=max_chars, profile="audit", emit=True)
    ok = code == 1 and out.startswith("MARGIN_EXCEEDED line 1:")
    return ok, "code=%d out=%r" % (code, out)


def _run_margin_emit_pass():
    text = AUDIT_DRAFT_VALID
    max_chars = _doc_length(text) * 2
    code, out = _capture_run(text, max_chars=max_chars, profile="audit", emit=True)
    ok = code == 0 and out == text
    return ok, "code=%d out=%r" % (code, out)


def _run_margin_iteration_also_fails():
    text = AUDIT_DRAFT_VALID
    max_chars = _doc_length(text)
    code, out = _capture_run(text, max_chars=max_chars, profile="audit")
    ok = code == 1 and out.startswith("MARGIN_EXCEEDED line 1:")
    return ok, "code=%d out=%r" % (code, out)


def _run_margin_no_max_chars_ok():
    code, out = _capture_run(
        "x" * 100 + "\n", max_chars=None, profile="basic", emit=True, min_margin_pct=8
    )
    ok = code == 0 and out == "x" * 100 + "\n"
    return ok, "code=%d out=%r" % (code, out)


RUN_TESTS = [
    ("emit clean echoes draft exactly", _run_emit_echo),
    ("no emit prints PASS line", _run_no_emit_pass),
    ("emit echo respects max-chars pass", _run_emit_echo_with_max_chars),
    ("emit with errors still exits 1 and prints errors", _run_emit_error),
    ("http url error quotes only the url", _run_http_quote),
    ("contract neither flag exits 2 MAX_CHARS_REQUIRED", _run_contract_missing_both_cli),
    ("contract both flags exits 2 MAX_CHARS_REQUIRED", _run_contract_given_both_cli),
    ("contract max-chars only runs clean audit", _run_contract_pass_max_chars_cli),
    ("contract no-max-chars only runs clean audit", _run_contract_pass_no_max_chars_cli),
    ("length contract helper pass/fail matrix", _run_contract_helper),
    ("margin requires --max-chars CLI exit 2", _run_margin_requires_max_chars_cli),
    ("margin emit fail MARGIN_EXCEEDED", _run_margin_emit_fail),
    ("margin emit pass within headroom", _run_margin_emit_pass),
    ("margin iteration also flags early", _run_margin_iteration_also_fails),
    ("margin no-max-chars not applied", _run_margin_no_max_chars_ok),
]


def self_test():
    failures = 0
    total = len(SELF_TESTS) + len(RUN_TESTS)
    for name, text, opts, expected in SELF_TESTS:
        got = [c for c, _, _ in lint(
            text,
            opts.get("max_chars"),
            opts.get("profile", "basic"),
            opts.get("min_margin_pct", 8),
        )]
        if got == expected:
            sys.stdout.write("ok   %s\n" % name)
        else:
            failures += 1
            sys.stdout.write("FAIL %s: expected codes %s, got %s\n" % (name, expected, got))
    for name, fn in RUN_TESTS:
        ok, msg = fn()
        if ok:
            sys.stdout.write("ok   %s\n" % name)
        else:
            failures += 1
            sys.stdout.write("FAIL %s: %s\n" % (name, msg))
    if failures:
        sys.stdout.write("self-test: %d/%d FAILED\n" % (failures, total))
        return 1
    sys.stdout.write("self-test: %d/%d PASSED\n" % (total, total))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Evidence-integrity linter for siftline-research drafts."
    )
    parser.add_argument("--file", metavar="PATH", help="draft file to lint (default: stdin)")
    parser.add_argument(
        "--max-chars", type=int, default=None,
        help="maximum document length in chars; audit/discovery/coverage require "
             "exactly one of --max-chars or --no-max-chars",
    )
    parser.add_argument(
        "--min-margin-pct", type=int, default=None,
        help="keep at least P%% headroom below --max-chars (default 8 when "
             "--max-chars is given); exceeding (100-P)%% of the cap is "
             "MARGIN_EXCEEDED. Requires --max-chars on structured profiles.",
    )
    parser.add_argument(
        "--no-max-chars", action="store_true",
        help="explicitly allow unlimited length; for audit/discovery/coverage, "
             "exactly one of --max-chars or --no-max-chars is required",
    )
    parser.add_argument(
        "--profile", choices=list(PROFILES), default="basic",
        help="structure profile: %s (default: basic)" % ", ".join(PROFILES),
    )
    parser.add_argument(
        "--emit", action="store_true",
        help="print the input draft exactly on a clean result instead of the PASS line",
    )
    parser.add_argument(
        "--self-test", action="store_true",
        help="run representative pass/fail cases instead of linting input",
    )
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()
    contract = _length_contract_error(args.profile, args.max_chars, args.no_max_chars)
    if contract:
        sys.stderr.write("%s: %s\n" % (contract[0], contract[1]))
        return 2
    margin_contract = _margin_contract_error(args.profile, args.max_chars, args.min_margin_pct)
    if margin_contract:
        sys.stderr.write("%s: %s\n" % (margin_contract[0], margin_contract[1]))
        return 2
    min_margin_pct = args.min_margin_pct if args.min_margin_pct is not None else 8
    if args.file:
        with open(args.file, "r", encoding="utf-8") as fh:
            text = fh.read()
    else:
        text = sys.stdin.read()
    return run_lint(text, args.max_chars, args.profile, args.emit, min_margin_pct)


if __name__ == "__main__":
    sys.exit(main())
