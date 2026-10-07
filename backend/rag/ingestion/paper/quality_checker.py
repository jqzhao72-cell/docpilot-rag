from dataclasses import dataclass
from typing import List

from .schemas import FigureData, TableData


@dataclass
class QualityResult:
    score: float
    level: str
    reasons: List[str]
    use_cloud: bool


def clamp_score(score: float) -> float:
    return max(0.0, min(1.0, score))


def get_quality_level(score: float) -> str:

    if score >= 0.8:
        return "good"

    if score >= 0.5:
        return "medium"

    return "bad"


# =========================================================
# OCR质量评估
# =========================================================

def evaluate_ocr(
    ocr_text: str,
    avg_confidence: float = None
) -> QualityResult:

    score = 1.0
    reasons = []

    text = (ocr_text or "").strip()

    if not text:

        score -= 0.7
        reasons.append("OCR结果为空")

    elif len(text) < 20:

        score -= 0.4
        reasons.append("OCR文本过短")

    elif len(text) < 50:

        score -= 0.2
        reasons.append("OCR有效文本较少")


    if avg_confidence is not None:

        if avg_confidence < 0.5:

            score -= 0.4
            reasons.append(
                f"OCR平均置信度过低: {avg_confidence:.2f}"
            )

        elif avg_confidence < 0.75:

            score -= 0.2
            reasons.append(
                f"OCR平均置信度一般: {avg_confidence:.2f}"
            )


    score = clamp_score(score)

    level = get_quality_level(score)

    return QualityResult(
        score=score,
        level=level,
        reasons=reasons,
        use_cloud=(score < 0.8)
    )


# =========================================================
# Figure质量评估
# =========================================================

def evaluate_figure(
    figure: FigureData,
    page_width: float,
    page_height: float
) -> QualityResult:

    score = 1.0
    reasons = []


    if not figure.caption:

        score -= 0.2
        reasons.append(
            "Figure缺少caption"
        )


    ocr_text = (
        figure.ocr_text or ""
    ).strip()


    if not ocr_text:

        score -= 0.3
        reasons.append(
            "Figure OCR为空"
        )

    elif len(ocr_text) < 30:

        score -= 0.2
        reasons.append(
            "Figure OCR文本较少"
        )


    suspicious_words = [
        "published online",
        "doi:",
        "copyright",
        "journal",
        "article",
    ]


    lower_text = ocr_text.lower()


    for word in suspicious_words:

        if word in lower_text:

            score -= 0.15

            reasons.append(
                f"Figure OCR包含疑似页面正文/页眉: {word}"
            )

            break


    score = clamp_score(score)

    level = get_quality_level(score)

    return QualityResult(
        score=score,
        level=level,
        reasons=reasons,
        use_cloud=(score < 0.8)
    )


# =========================================================
# Table质量评估
# =========================================================

def evaluate_table(
    table: TableData
) -> QualityResult:

    score = 1.0
    reasons = []


    rows = table.rows


    if not rows:

        score -= 0.7
        reasons.append(
            "Table没有任何行"
        )

    else:

        row_lengths = [
            len(row)
            for row in rows
        ]


        max_columns = max(
            row_lengths
        )


        if max_columns <= 1:

            score -= 0.4
            reasons.append(
                "Table列数异常"
            )


        total_cells = 0
        empty_cells = 0


        for row in rows:

            for cell in row:

                total_cells += 1

                if cell is None or not str(cell).strip():

                    empty_cells += 1


        if total_cells > 0:

            empty_ratio = (
                empty_cells
                / total_cells
            )

            if empty_ratio > 0.6:

                score -= 0.4

                reasons.append(
                    f"空单元格比例过高: "
                    f"{empty_ratio:.2f}"
                )

            elif empty_ratio > 0.35:

                score -= 0.2

                reasons.append(
                    f"空单元格较多: "
                    f"{empty_ratio:.2f}"
                )


    if not table.caption:

        score -= 0.1

        reasons.append(
            "Table缺少caption"
        )


    score = clamp_score(score)

    level = get_quality_level(score)


    return QualityResult(
        score=score,
        level=level,
        reasons=reasons,
        use_cloud=(score < 0.8)
    )