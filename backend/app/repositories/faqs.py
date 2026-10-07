"""FAQ のデータアクセスと検索。AI Agent の FAQ 検索 Tool からも利用する。

検索は少量の FAQ を前提とした「キーワード + 部分一致」のスコア方式。
FAQ を全件読み込み、Python で採点するため SQLite / PostgreSQL で結果が同じになる。
件数が増えた場合は、関数のシグネチャを保ったまま全文検索・ベクトル検索に置き換える。
"""

import unicodedata
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Faq

# スコアの重み
KEYWORD_SCORE = 3  # FAQ のキーワードが質問文に含まれる
QUESTION_SCORE = 2  # 質問文（全体）が FAQ の質問に含まれる
ANSWER_SCORE = 1  # 質問文（全体）が FAQ の回答に含まれる
TERM_SCORE = 1  # 空白で区切った語が FAQ の質問・キーワードに含まれる


@dataclass(frozen=True)
class FaqMatch:
    faq: Faq
    score: int


def normalize(text: str) -> str:
    """全角・半角と大文字・小文字の違いを吸収する（NFKC + casefold）。"""
    return unicodedata.normalize("NFKC", text).casefold().strip()


def score_faq(faq: Faq, query: str) -> int:
    """正規化済みの質問文 query に対する FAQ のスコア（0 は不一致）。"""
    question = normalize(faq.question)
    answer = normalize(faq.answer)
    keywords = [normalize(keyword) for keyword in faq.keywords.split()]

    score = KEYWORD_SCORE * sum(1 for keyword in keywords if keyword and keyword in query)
    if query in question:
        score += QUESTION_SCORE
    if query in answer:
        score += ANSWER_SCORE

    terms = query.split()
    if len(terms) > 1:
        searchable = " ".join([question, *keywords])
        score += TERM_SCORE * sum(1 for term in terms if term in searchable)
    return score


def search_faqs(session: Session, q: str | None = None, *, limit: int = 5) -> list[FaqMatch]:
    """FAQ を検索する。スコアの高い順（同点は id の昇順）に最大 limit 件を返す。

    q が空の場合は id 順に limit 件を返す（スコアは 0）。
    """
    faqs = session.scalars(select(Faq).order_by(Faq.id)).all()
    query = normalize(q or "")
    if not query:
        return [FaqMatch(faq=faq, score=0) for faq in faqs[:limit]]

    matches = [FaqMatch(faq=faq, score=score_faq(faq, query)) for faq in faqs]
    matches = [match for match in matches if match.score > 0]
    matches.sort(key=lambda match: (-match.score, match.faq.id))
    return matches[:limit]
