"""FAQ の初期データ（10 件）。Demo 1 の問い合わせ例に対応する社内ヘルプデスクの FAQ。

keywords は空白区切り。利用者の質問文にキーワードが含まれるかで一致を判定するため、
表記ゆれ（Wi-Fi / WiFi / 無線LAN など）は個別のキーワードとして並べる。
「申請」のように多くの質問に現れる汎用的な語は、無関係な FAQ に一致するためキーワードにしない。
"""

from typing import TypedDict

from app.models import InquiryCategory


class SeedFaq(TypedDict):
    question: str
    answer: str
    category: InquiryCategory
    keywords: str


SEED_FAQS: list[SeedFaq] = [
    {
        "question": "パスワードを忘れてログインできません",
        "answer": "社内ポータルのログイン画面にある「パスワードをお忘れの方」から再設定してください。"
        "登録済みの社用メールアドレスに再設定用のリンクが届きます（有効期限は 30 分）。"
        "メールが届かない場合はヘルプデスクへ問い合わせてください。",
        "category": InquiryCategory.ACCOUNT,
        "keywords": "パスワード 忘れ リセット 再設定 ログイン",
    },
    {
        "question": "新入社員のアカウントを発行してほしい",
        "answer": "入社日の 5 営業日前までに、上長から「アカウント発行申請」フォームで申請してください。"
        "メールアカウントと社内システムのアカウントがまとめて発行されます。",
        "category": InquiryCategory.ACCOUNT,
        "keywords": "新入社員 入社 アカウント発行 発行",
    },
    {
        "question": "退職者のアカウントを無効化したい",
        "answer": "退職日が決まったら、上長または人事担当者が「アカウント停止申請」フォームで申請してください。"
        "退職日の業務終了後にアカウントが無効化されます。",
        "category": InquiryCategory.ACCOUNT,
        "keywords": "退職 退職者 無効化 停止 削除",
    },
    {
        "question": "多要素認証（MFA）の認証アプリを再設定したい",
        "answer": "スマートフォンの機種変更などで認証アプリが使えなくなった場合は、本人確認のうえ"
        "ヘルプデスクで MFA をリセットします。リセット後、次回ログイン時に新しい端末で再登録してください。",
        "category": InquiryCategory.ACCOUNT,
        "keywords": "多要素認証 MFA 二段階認証 認証アプリ 機種変更",
    },
    {
        "question": "社内 Wi-Fi に接続できません",
        "answer": "SSID「corp-wifi」を選び、社員番号とパスワードで接続してください。接続できない場合は、"
        "端末の Wi-Fi をオフ／オンし、保存済みのネットワーク設定を削除してから再接続してください。"
        "特定の会議室だけで接続できない場合は、場所を添えてヘルプデスクへ連絡してください。",
        "category": InquiryCategory.NETWORK,
        "keywords": "Wi-Fi WiFi 無線 無線LAN 接続できない ネットワーク",
    },
    {
        "question": "VPN が頻繁に切断されます",
        "answer": "VPN クライアントを最新版に更新し、自宅のルーターを再起動してください。"
        "30 分程度で切断される場合は、省電力設定でネットワークアダプターがスリープしていないか確認してください。"
        "改善しない場合は、切断時刻を添えて問い合わせてください。",
        "category": InquiryCategory.NETWORK,
        "keywords": "VPN 切断 切れる 在宅 リモート",
    },
    {
        "question": "Excel や Word が起動直後に終了します",
        "answer": "Office アプリを「修復」してください（設定 → アプリ → Microsoft 365 → 変更 → クイック修復）。"
        "Windows Update の直後に発生した場合は、PC を再起動してから再度お試しください。",
        "category": InquiryCategory.SOFTWARE,
        "keywords": "Excel Word Office 起動 強制終了 落ちる",
    },
    {
        "question": "ソフトウェアのライセンスを追加したい",
        "answer": "「ソフトウェア利用申請」フォームで、ソフトウェア名・利用者・利用期間を入力して申請してください。"
        "承認後、ライセンスの割り当てとインストール手順をメールで案内します。",
        "category": InquiryCategory.SOFTWARE,
        "keywords": "ライセンス 追加 購入 インストール ソフトウェア",
    },
    {
        "question": "複合機で両面印刷ができません",
        "answer": "印刷ダイアログの「プリンターのプロパティ」で「両面印刷」を選んでください。"
        "選択肢がない場合はプリンタードライバーが古い可能性があるため、ポータルから最新のドライバーを入れ直してください。",
        "category": InquiryCategory.OTHER,
        "keywords": "複合機 プリンター プリンタ 印刷 両面 ドライバー",
    },
    {
        "question": "PC が故障したので代替機を借りたい",
        "answer": "ヘルプデスク窓口（3 階）で代替機を貸し出しています。故障した PC を持参し、"
        "貸出申請書に記入してください。データの移行が必要な場合は事前に連絡してください。",
        "category": InquiryCategory.OTHER,
        "keywords": "PC パソコン 故障 代替機 貸出 交換",
    },
]
